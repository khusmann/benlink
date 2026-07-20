import asyncio
import hashlib
import typing as t

import pytest

from benlink.command import CommandConnection
from benlink.firmware import flash
from benlink.firmware._flash import FlashError, FlashResult
import benlink.protocol as p
from benlink.protocol.command.bt_notification import (
    BtEventNotificationBody, BtEventType,
)
from benlink.protocol.command.vm import (
    UpdateError,
    UpdateState,
    VmConnectReplyBody,
    VmControlReplyBody,
    VmControlType,
    VmControlUpdateData,
    VmControlUpdateDataBytesReq,
    VmControlUpdateError,
    VmControlUpdateStartCfm,
    VmControlUpdateSyncCfm,
    VmControlUpdateSyncReq,
    VmControlUpdateTransferCompleteRes,
    VmuPacket,
    VmuPacketType,
    UpdateStartCfmCode,
    VmControlBody,
    VmControlUpdateCompleteInd,
    VmControlUpdateTransferCompleteInd,
)

CHUNK = 145


class FakeRadio:
    """A radio that answers the update messages the way the captures do.

    Everything is round-tripped through `to_bytes`/`from_bytes` so the test
    exercises real serialization in both directions.
    """

    def __init__(
        self,
        state: UpdateState = UpdateState.DATA_TRANSFER,
        chunk: int = CHUNK,
        skip_first: int = 0,
        error_after: int | None = None,
        preempt_sync: bool = False,
        interrupt_after: int | None = None,
        interrupt_abort_too: bool = False,
        staged_tail: bytes | None = None,
    ):
        self.state = state
        self.chunk = chunk
        self.skip_first = skip_first
        self.error_after = error_after
        self.received = bytearray()
        self.sent: t.List[VmControlType] = []
        self.final_flags: t.List[bool] = []
        self.error_on_finalize = False
        self.preempt_sync = preempt_sync
        self.interrupt_after = interrupt_after
        self.interrupt_abort_too = interrupt_abort_too
        self.staged_tail = staged_tail
        self.disconnected = False
        self.aborted = False
        self._callback: t.Any = None
        self._chunks_served = 0

    # CommandLink

    def is_connected(self) -> bool:
        return True

    async def connect(self, callback: t.Any) -> None:
        self._callback = callback

    async def disconnect(self) -> None:
        pass

    async def send_bytes(self, data: bytes) -> None:
        raise AssertionError("flash should not use send_bytes")

    async def send(self, msg: p.Message) -> None:
        if (self.interrupt_after is not None
                and self.sent.count(VmControlType.UPDATE_DATA)
                >= self.interrupt_after):
            if not self.interrupt_abort_too:
                # One interrupt only, so the abort that follows can land.
                self.interrupt_after = None
            raise KeyboardInterrupt
        self._handle(p.Message.from_bytes(msg.to_bytes()))

    # Radio behaviour

    def _emit(self, command: p.ExtendedCommand, body: t.Any, is_reply: bool) -> None:
        out = p.Message(
            command_group=p.CommandGroup.EXTENDED,
            is_reply=is_reply,
            command=command,
            body=body,
        )
        self._callback(p.Message.from_bytes(out.to_bytes()))

    def _emit_vmu(self, packet_type: VmuPacketType, msg: t.Any) -> None:
        packet = VmuPacket(
            vmu_packet_type=packet_type,
            n_bytes_payload=len(msg.to_bytes()),
            msg=msg,
        )
        self._emit(
            p.ExtendedCommand.BT_EVENT_NOTIFICATION,
            BtEventNotificationBody(
                bt_event_type=BtEventType.VMU_PACKET, bt_event=packet
            ),
            is_reply=False,
        )

    def _request_bytes(self) -> None:
        skip = self.skip_first if self._chunks_served == 0 else 0
        self._chunks_served += 1
        self._emit_vmu(
            VmuPacketType.UPDATE_DATA_BYTES_REQ,
            VmControlUpdateDataBytesReq(
                n_bytes_requested=self.chunk, n_bytes_skip=skip
            ),
        )

    def _emit_sync_cfm(self, md5_tail: bytes) -> None:
        self._emit_vmu(
            VmuPacketType.UPDATE_SYNC_CFM,
            VmControlUpdateSyncCfm(
                update_state=self.state, md5sum_tail=md5_tail, unknown=b"\x00"
            ),
        )

    def _handle(self, msg: p.Message) -> None:
        if msg.command == p.ExtendedCommand.VM_CONNECT:
            self._emit(
                p.ExtendedCommand.VM_CONNECT,
                VmConnectReplyBody(status=p.ReplyStatus.SUCCESS),
                is_reply=True,
            )
            if self.preempt_sync:
                # Answers a question that has not been asked yet.
                self._emit_sync_cfm(
                    self.staged_tail or b"\x00\x00\x00\x00")
            return

        if msg.command == p.ExtendedCommand.VM_DISCONNECT:
            self.disconnected = True
            return

        body = msg.body
        assert isinstance(body, VmControlBody)
        self.sent.append(body.vm_control_type)

        # Every VM_CONTROL is acknowledged before the answer arrives.
        self._emit(
            p.ExtendedCommand.VM_CONTROL,
            VmControlReplyBody(status=p.ReplyStatus.SUCCESS),
            is_reply=True,
        )

        match body.vm_control_type:
            case VmControlType.UPDATE_SYNC_REQ:
                assert isinstance(body.msg, VmControlUpdateSyncReq)
                if not self.preempt_sync:
                    self._emit_sync_cfm(
                        self.staged_tail or body.msg.md5sum_tail)
            case VmControlType.UPDATE_START_REQ:
                self._emit_vmu(
                    VmuPacketType.UPDATE_START_CFM,
                    VmControlUpdateStartCfm(
                        cfm_code=UpdateStartCfmCode.OK, unknown=b"\x00\x00"
                    ),
                )
            case VmControlType.UPDATE_START_DATA_REQ:
                self._request_bytes()
            case VmControlType.UPDATE_DATA:
                assert isinstance(body.msg, VmControlUpdateData)
                self.received += body.msg.data
                self.final_flags.append(body.msg.is_final_fragment)
                if self.error_after is not None and \
                        len(self.received) >= self.error_after:
                    self._emit_vmu(
                        VmuPacketType.UPDATE_ERROR,
                        VmControlUpdateError(
                            update_error=UpdateError.BATTERY_LOW),
                    )
                elif not body.msg.is_final_fragment:
                    self._request_bytes()
            case VmControlType.UPDATE_IS_VALIDATION_DONE_REQ:
                self._emit_vmu(
                    VmuPacketType.UPDATE_TRANSFER_COMPLETE_IND,
                    VmControlUpdateTransferCompleteInd(),
                )
            case VmControlType.UPDATE_IN_PROGRESS_RES:
                if self.error_on_finalize:
                    self._emit_vmu(
                        VmuPacketType.UPDATE_ERROR,
                        VmControlUpdateError(update_error=UpdateError.UNKNOWN),
                    )
                else:
                    self._emit_vmu(
                        VmuPacketType.UPDATE_COMPLETE_IND,
                        VmControlUpdateCompleteInd(),
                    )
            case VmControlType.UPDATE_ABORT_REQ:
                self.aborted = True
            case VmControlType.UPDATE_TRANSFER_COMPLETE_RES:
                # Acked like every control message; the reboot is the answer.
                pass
            case _:
                raise AssertionError(
                    f"flash sent an unexpected {body.vm_control_type.name}"
                )


def _run(radio: FakeRadio, image: bytes, **kwargs: t.Any) -> FlashResult:
    async def main() -> FlashResult:
        conn = CommandConnection(radio)
        await conn.connect()
        return await flash(conn, image, **kwargs)

    return asyncio.run(main())


def test_transfer_phase_sends_whole_image():
    data = bytes(range(256)) * 5
    radio = FakeRadio()

    result = _run(radio, data)

    assert result == "REBOOT_PENDING"
    assert bytes(radio.received) == data
    assert radio.sent[-1] == VmControlType.UPDATE_TRANSFER_COMPLETE_RES


def test_final_fragment_is_flagged_once_at_the_end():
    data = b"x" * (CHUNK * 3)
    radio = FakeRadio()
    _run(radio, data)

    # The radio stops asking for more only because the last UPDATE_DATA said so,
    # and an image that divides evenly into chunks must still flag its last one.
    assert radio.final_flags == [False, False, True]


def test_image_shorter_than_one_chunk():
    data = b"tiny"
    radio = FakeRadio()

    assert _run(radio, data) == "REBOOT_PENDING"
    assert bytes(radio.received) == data


def test_progress_reports_reach_the_total():
    data = b"y" * (CHUNK * 2 + 7)
    seen: t.List[t.Tuple[str, int, int]] = []

    def record(label: str, done: int, total: int) -> None:
        seen.append((label, done, total))

    _run(FakeRadio(), data, progress=record)

    assert [n for _, n, _ in seen] == [CHUNK, CHUNK * 2, len(data)]
    assert all(total == len(data) for _, _, total in seen)


def test_resume_honours_n_bytes_skip():
    data = bytes(range(256)) * 4
    radio = FakeRadio(skip_first=300)

    _run(radio, data)

    # The radio already had the first 300 bytes, so they are never resent.
    assert bytes(radio.received) == data[300:]


def test_in_progress_state_finalizes_instead_of_transferring():
    radio = FakeRadio(state=UpdateState.IN_PROGRESS)

    result = _run(radio, b"unused")

    assert result == "COMPLETE"
    assert VmControlType.UPDATE_DATA not in radio.sent
    assert VmControlType.UPDATE_IN_PROGRESS_RES in radio.sent
    assert radio.disconnected


def test_transfer_complete_state_only_asks_for_the_reboot():
    radio = FakeRadio(state=UpdateState.TRANSFER_COMPLETE)

    result = _run(radio, b"unused")

    assert result == "REBOOT_PENDING"
    assert VmControlType.UPDATE_DATA not in radio.sent
    assert radio.sent[-1] == VmControlType.UPDATE_TRANSFER_COMPLETE_RES


def test_reboot_request_asks_the_radio_to_restart_now():
    """The byte is 0 on the app's success path; 1 is its "cancel restart"."""
    radio = FakeRadio(state=UpdateState.TRANSFER_COMPLETE)
    sent: t.List[p.Message] = []
    original = radio.send

    async def record(msg: p.Message) -> None:
        sent.append(msg)
        await original(msg)

    radio.send = record  # type: ignore[method-assign]
    _run(radio, b"unused")

    final = sent[-1]
    assert isinstance(final.body, VmControlBody)
    assert isinstance(final.body.msg, VmControlUpdateTransferCompleteRes)
    assert final.body.msg.is_complete is False


def test_update_error_is_raised_not_waited_out():
    radio = FakeRadio(error_after=CHUNK)

    with pytest.raises(FlashError, match="BATTERY_LOW"):
        _run(radio, b"z" * CHUNK * 10)

    assert radio.aborted


def test_failure_after_staging_does_not_abort():
    """Aborting here would discard an image the radio has already validated."""
    radio = FakeRadio(state=UpdateState.IN_PROGRESS)
    radio.error_on_finalize = True

    with pytest.raises(FlashError):
        _run(radio, b"unused")

    assert not radio.aborted


def test_reply_arriving_before_it_is_awaited_is_not_lost():
    """The subscription is opened before the first send and held for the whole
    flash, so a radio that answers early is buffered rather than dropped."""
    image = b"unused"
    radio = FakeRadio(state=UpdateState.TRANSFER_COMPLETE, preempt_sync=True,
                      staged_tail=hashlib.md5(image).digest()[-4:])

    assert _run(radio, image) == "REBOOT_PENDING"
    assert radio.sent[-1] == VmControlType.UPDATE_TRANSFER_COMPLETE_RES


def test_interrupt_mid_transfer_still_tells_the_radio():
    """Ctrl+C is not an `Exception`, but the radio is left mid-transfer."""
    radio = FakeRadio(interrupt_after=3)

    with pytest.raises(KeyboardInterrupt):
        _run(radio, b"x" * CHUNK * 100)

    assert radio.aborted
    assert radio.sent.count(VmControlType.UPDATE_DATA) == 3


def test_second_interrupt_is_not_swallowed_by_the_abort():
    radio = FakeRadio(interrupt_after=3, interrupt_abort_too=True)

    with pytest.raises(KeyboardInterrupt):
        _run(radio, b"x" * CHUNK * 100)

    assert not radio.aborted


def test_refuses_to_finish_someone_elses_update():
    """A radio holding a different image must not be committed by mistake."""
    radio = FakeRadio(state=UpdateState.IN_PROGRESS, staged_tail=b"\xde\xad\xbe\xef")

    with pytest.raises(FlashError, match="different image"):
        _run(radio, b"unused")

    assert VmControlType.UPDATE_IN_PROGRESS_RES not in radio.sent
