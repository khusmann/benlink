"""Delivering an assembled firmware image to a radio.

**This can break your radio, and nothing in this library can undo it.
Use this at your own risk. I am not responsible for bricking your radio.**

The transfer runs over the same command connection as everything else, in two
phases separated by a reboot:

    VM_CONNECT
    UPDATE_SYNC_REQ          -> UPDATE_SYNC_CFM (DATA_TRANSFER)
    UPDATE_START_REQ         -> UPDATE_START_CFM
    UPDATE_START_DATA_REQ
    UPDATE_DATA              <- UPDATE_DATA_BYTES_REQ   (repeats)
    UPDATE_IS_VALIDATION_DONE_REQ
                             -> UPDATE_TRANSFER_COMPLETE_IND
    UPDATE_TRANSFER_COMPLETE_RES

    [radio reboots, connection drops, reconnect]

    VM_CONNECT
    UPDATE_SYNC_REQ          -> UPDATE_SYNC_CFM (IN_PROGRESS)
    UPDATE_START_REQ         -> UPDATE_START_CFM
    UPDATE_IN_PROGRESS_RES   -> UPDATE_COMPLETE_IND
    VM_DISCONNECT

`flash` runs one phase per call and reports whether a reboot is pending, so the
caller owns the reconnect. Which phase runs is decided by the `UpdateState` the
radio reports in `UPDATE_SYNC_CFM` rather than tracked locally, so an update
interrupted after the image was staged resumes at the right phase rather than
sending it all again. An interrupted *transfer* is not resumable: the radio
starts it over from the beginning.
"""

from __future__ import annotations
import asyncio
import hashlib
import typing as t

from .. import protocol as p
from ..protocol.command.bt_notification import (
    BtEventNotificationBody, BtEventType,
)
from ..protocol.command.vm import (
    UpdateState,
    VmConnectBody,
    VmConnectReplyBody,
    VmControlBody,
    VmControlReplyBody,
    VmControlMessage,
    VmControlType,
    VmControlUpdateAbortReq,
    VmControlUpdateData,
    VmControlUpdateDataBytesReq,
    VmControlUpdateDataStartReq,
    VmControlUpdateError,
    VmControlUpdateInProgressRes,
    VmControlUpdateIsValidationDoneReq,
    VmControlUpdateStartReq,
    VmControlUpdateSyncCfm,
    VmControlUpdateSyncReq,
    VmControlUpdateTransferCompleteRes,
    VmDisconnectBody,
    VmuPacket,
    VmuPacketMessage,
    VmuPacketType,
)
from ._fetch import ProgressCallback

if t.TYPE_CHECKING:
    from ..command import (
        CommandConnection, RadioMessage, UnknownProtocolMessage,
    )

_REPLY_TIMEOUT = 15.0
_CHUNK_TIMEOUT = 60.0
_VALIDATION_TIMEOUT = 180.0
_COMPLETE_TIMEOUT = 180.0

# The radio reboots on its own once it accepts UPDATE_TRANSFER_COMPLETE_RES, so
# this byte is not "did the transfer succeed" despite the field name: 0 proceeds
# with the reboot, 1 postpones it. All successful updates in my btsnoop
# captures send 0; the one sending 1 is the app's "cancel the restart" button,
# after which the radio sits in TRANSFER_COMPLETE until a later session sends 0.
_REBOOT_NOW = False


FlashResult = t.Literal["REBOOT_PENDING", "COMPLETE"]
"""What `flash` left the radio doing.

`REBOOT_PENDING`: the image is staged, and the radio is rebooting. The connection
will drop; reconnect and call `flash` again to finish.

`COMPLETE`: the update is committed and running.
"""


async def flash(
    conn: CommandConnection,
    image: bytes,
    progress: ProgressCallback | None = None,
) -> FlashResult:
    """Deliver an assembled firmware image to a connected radio.

    **This can break your radio, and nothing in this library can undo it.
    Use this at your own risk. I am not responsible for bricking your radio.**

    Runs whichever phase of the update the radio says it is in, so a full update
    is two calls with a reconnect in between:

        if await flash(conn, image) == "REBOOT_PENDING":
            ... reconnect ...
            await flash(conn, image)

    Raises `FlashError` if the radio is partway through a *different* image, so
    that finishing an update never commits something the caller didn't pass.
    """
    async with conn.subscribe(_is_vm_message) as inbox:
        await _vm_connect(conn, inbox)

        tail = _md5_tail(image)
        cfm = await _sync(conn, inbox, tail)
        if cfm.md5sum_tail != tail:
            # UpdateError.SYNC_IS_DIFFERENT suggests the radio rejects this
            # itself, but no capture shows it doing so, and committing the wrong
            # image is not something to find out about the hard way.
            raise FlashError(
                f"radio is partway through a different image: it reports "
                f"md5 ...{cfm.md5sum_tail.hex()}, this one is ...{tail.hex()}. "
                f"Flash the matching image to finish that update, or call "
                f"abort_update to discard it"
            )

        state = cfm.update_state
        await _start(conn, inbox)

        match state:
            case UpdateState.DATA_TRANSFER | UpdateState.VALIDATION:
                # Only the transfer is abortable. Once an image is staged the
                # radio owns it, and UPDATE_ABORT_REQ would throw it away.
                try:
                    if state is UpdateState.DATA_TRANSFER:
                        await _transfer(conn, inbox, image, progress)
                    # VALIDATION appears in no capture. The image is already
                    # delivered in that state, so ask whether the checksum
                    # finished rather than sending all of it again.
                    await _validate(conn, inbox)
                except (Exception, KeyboardInterrupt, asyncio.CancelledError):
                    # Ctrl+C and cancellation are not `Exception`, but a radio
                    # left mid-transfer still deserves to be told.
                    await _abort(conn)
                    raise
                await _request_reboot(conn)
                return "REBOOT_PENDING"

            case UpdateState.TRANSFER_COMPLETE:
                await _request_reboot(conn)
                return "REBOOT_PENDING"

            case UpdateState.IN_PROGRESS:
                await _finalize(conn, inbox)
                return "COMPLETE"

            case UpdateState.COMMIT:
                # UPDATE_COMMIT_CFM exists, but no capture shows the app in this
                # state or sending it, so there is nothing to copy. Stopping
                # leaves the staged image intact for the app to finish.
                raise FlashError(
                    "radio reports the COMMIT state, which benlink has never "
                    "observed and does not know how to answer"
                )


async def abort_update(conn: CommandConnection) -> None:
    """Discard whatever update the radio is partway through.

    The way out when an image has been staged but the file that produced it is
    gone: `flash` refuses to finish an update it cannot identify, and without
    this there would be nothing left to try.
    """
    async with conn.subscribe(_is_vm_message) as inbox:
        await _vm_connect(conn, inbox)
        await _send_control(
            conn, VmControlType.UPDATE_ABORT_REQ, VmControlUpdateAbortReq()
        )
        await _recv_vmu(inbox, VmuPacketType.UPDATE_ABORT_CFM)
        await conn.send_protocol_message(
            _message(p.ExtendedCommand.VM_DISCONNECT, VmDisconnectBody())
        )


#####################
# Phases

async def _transfer(
    conn: CommandConnection,
    inbox: asyncio.Queue[RadioMessage],
    image: bytes,
    progress: ProgressCallback | None,
) -> None:
    """Send the image, one device-requested chunk at a time."""
    await _send_control(
        conn, VmControlType.UPDATE_START_DATA_REQ, VmControlUpdateDataStartReq()
    )

    total = len(image)
    offset = 0

    while offset < total:
        req = await _recv_vmu_as(
            inbox,
            VmuPacketType.UPDATE_DATA_BYTES_REQ,
            VmControlUpdateDataBytesReq,
            timeout=_CHUNK_TIMEOUT,
        )

        # Always 0 in the captures, including across aborted transfers, which
        # the radio restarts rather than resumes. Honoured in case some model
        # does ask, but the relative reading is a guess with nothing to check
        # it against.
        offset += req.n_bytes_skip

        chunk = image[offset:offset + req.n_bytes_requested]
        if not chunk:
            raise FlashError(
                f"radio asked for {req.n_bytes_requested} bytes at offset "
                f"{offset}, past the end of a {total} byte image"
            )

        offset += len(chunk)

        await _send_control(
            conn,
            VmControlType.UPDATE_DATA,
            VmControlUpdateData(
                is_final_fragment=offset >= total,
                data=chunk,
            ),
        )

        if progress is not None:
            progress("flash", offset, total)


async def _validate(
    conn: CommandConnection, inbox: asyncio.Queue[RadioMessage]
) -> None:
    """Wait for the radio to checksum what it received."""
    await _send_control(
        conn,
        VmControlType.UPDATE_IS_VALIDATION_DONE_REQ,
        VmControlUpdateIsValidationDoneReq(),
    )
    await _recv_vmu(
        inbox,
        VmuPacketType.UPDATE_TRANSFER_COMPLETE_IND,
        timeout=_VALIDATION_TIMEOUT,
    )


async def _request_reboot(conn: CommandConnection) -> None:
    """Release the staged image, which the radio reboots into on its own.

    A radio that ignores this stays in `TRANSFER_COMPLETE`, and that state
    dispatches straight back here, so calling `flash` again re-sends the same
    message rather than making progress.

    Confirmed on the UV-Pro (260) and the GA-5WB (259), which takes the same
    image as the VR-N76. Other models are untested.
    """
    await _send_control(
        conn,
        VmControlType.UPDATE_TRANSFER_COMPLETE_RES,
        VmControlUpdateTransferCompleteRes(is_complete=_REBOOT_NOW),
    )


async def _finalize(
    conn: CommandConnection, inbox: asyncio.Queue[RadioMessage]
) -> None:
    """Commit the staged image on the rebooted radio."""
    await _send_control(
        conn, VmControlType.UPDATE_IN_PROGRESS_RES, VmControlUpdateInProgressRes()
    )
    await _recv_vmu(
        inbox, VmuPacketType.UPDATE_COMPLETE_IND, timeout=_COMPLETE_TIMEOUT
    )

    await conn.send_protocol_message(
        _message(p.ExtendedCommand.VM_DISCONNECT, VmDisconnectBody())
    )


async def _vm_connect(
    conn: CommandConnection, inbox: asyncio.Queue[RadioMessage]
) -> None:
    await conn.send_protocol_message(
        _message(p.ExtendedCommand.VM_CONNECT, VmConnectBody())
    )
    reply = await _recv_connect_reply(inbox)
    if reply.status != p.ReplyStatus.SUCCESS:
        raise FlashError(f"VM_CONNECT rejected: {reply.status.name}")


async def _sync(
    conn: CommandConnection, inbox: asyncio.Queue[RadioMessage], md5_tail: bytes
) -> VmControlUpdateSyncCfm:
    await _send_control(
        conn,
        VmControlType.UPDATE_SYNC_REQ,
        VmControlUpdateSyncReq(md5sum_tail=md5_tail),
    )
    return await _recv_vmu_as(
        inbox, VmuPacketType.UPDATE_SYNC_CFM, VmControlUpdateSyncCfm
    )


async def _start(
    conn: CommandConnection, inbox: asyncio.Queue[RadioMessage]
) -> None:
    await _send_control(
        conn, VmControlType.UPDATE_START_REQ, VmControlUpdateStartReq()
    )
    # UPDATE_START_CFM carries a cfm_code, but every capture reports OK in both
    # phases, so nothing here can be keyed off it.
    await _recv_vmu(inbox, VmuPacketType.UPDATE_START_CFM)


async def _abort(conn: CommandConnection) -> None:
    """Best effort: the original failure is what the caller needs to see.

    Only `Exception` is swallowed, so a second Ctrl+C during the abort gets out
    rather than being absorbed by the cleanup.
    """
    try:
        await _send_control(
            conn, VmControlType.UPDATE_ABORT_REQ, VmControlUpdateAbortReq()
        )
    except Exception:
        pass


#####################
# Transport

def _md5_tail(image: bytes) -> bytes:
    """Last 4 bytes of the md5 digest, which is how UPDATE_SYNC_REQ names an
    image."""
    return hashlib.md5(image).digest()[-4:]


class FlashError(RuntimeError):
    """The radio rejected or abandoned the update."""


def _message(command: p.ExtendedCommand, body: t.Any) -> p.Message:
    return p.Message(
        command_group=p.CommandGroup.EXTENDED,
        is_reply=False,
        command=command,
        body=body,
    )


async def _send_control(
    conn: CommandConnection, control_type: VmControlType, msg: VmControlMessage
) -> None:
    await conn.send_protocol_message(_message(
        p.ExtendedCommand.VM_CONTROL,
        VmControlBody(
            vm_control_type=control_type,
            # Not msg.length(), which is None for the dynamically sized bodies.
            n_bytes_payload=len(msg.to_bytes()),
            msg=msg,
        ),
    ))


def _is_vm_message(msg: RadioMessage) -> bool:
    from ..command import UnknownProtocolMessage

    if not isinstance(msg, UnknownProtocolMessage):
        return False
    body = msg.message.body
    if isinstance(body, (VmConnectReplyBody, VmControlReplyBody)):
        return True
    return (
        isinstance(body, BtEventNotificationBody)
        and body.bt_event_type == BtEventType.VMU_PACKET
    )


_T = t.TypeVar("_T")


async def _with_timeout(
    receive: t.Coroutine[t.Any, t.Any, _T], timeout: float, described_as: str
) -> _T:
    # asyncio.timeout would read better, but it is 3.11+ and this package
    # supports 3.10.
    try:
        return await asyncio.wait_for(receive, timeout)
    except asyncio.TimeoutError:
        raise FlashError(
            f"radio went quiet: no {described_as} within {timeout:g}s"
        ) from None


async def _recv_body(inbox: asyncio.Queue[RadioMessage]) -> t.Any:
    """`_is_vm_message` has already established that these are VM messages."""
    msg = t.cast("UnknownProtocolMessage", await inbox.get())
    return msg.message.body


async def _recv_connect_reply(
    inbox: asyncio.Queue[RadioMessage], timeout: float = _REPLY_TIMEOUT
) -> VmConnectReplyBody:
    async def receive() -> VmConnectReplyBody:
        while True:
            body = await _recv_body(inbox)
            if isinstance(body, VmConnectReplyBody):
                return body

    return await _with_timeout(receive(), timeout, "VM_CONNECT reply")


async def _recv_vmu(
    inbox: asyncio.Queue[RadioMessage],
    expect: VmuPacketType,
    timeout: float = _REPLY_TIMEOUT,
) -> VmuPacketMessage | bytes:
    """Wait for a VMU packet of `expect`.

    The `VM_CONTROL` reply that comes back first only acknowledges receipt of
    the control message; the answer always follows separately as a VMU packet.
    An `UPDATE_ERROR` is raised here rather than left to time out.
    """
    async def receive() -> VmuPacketMessage | bytes:
        while True:
            body = await _recv_body(inbox)
            if not isinstance(body, BtEventNotificationBody):
                continue

            packet = body.bt_event
            if not isinstance(packet, VmuPacket):
                continue

            if isinstance(packet.msg, VmControlUpdateError):
                raise FlashError(
                    f"radio reported {packet.msg.update_error.name} while "
                    f"waiting for {expect.name}"
                )

            if packet.vmu_packet_type == expect:
                return packet.msg

    return await _with_timeout(receive(), timeout, expect.name)


_VmuT = t.TypeVar("_VmuT", bound=VmuPacketMessage)


async def _recv_vmu_as(
    inbox: asyncio.Queue[RadioMessage],
    expect: VmuPacketType,
    as_type: t.Type[_VmuT],
    timeout: float = _REPLY_TIMEOUT,
) -> _VmuT:
    """`_recv_vmu` for the packets whose fields are actually read."""
    msg = await _recv_vmu(inbox, expect, timeout)
    if not isinstance(msg, as_type):
        raise FlashError(f"could not parse {expect.name}: {msg!r}")
    return msg
