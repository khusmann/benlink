"""
Layer 3: GAIA BT firmware delivery over the VM RFCOMM channel.

The update is split into two phases separated by a radio reboot:

**Phase 1 — transfer:**
  VM_CONNECT → UPDATE_SYNC_REQ → UPDATE_START_REQ →
  UPDATE_DATA_START_REQ → [chunk loop driven by UPDATE_DATA_BYTES_REQ] →
  UPDATE_IS_VALIDATION_DONE_REQ → UPDATE_TRANSFER_COMPLETE_RES
  (radio reboots, BT connection drops)

**Phase 2 — confirm** (after reconnect):
  VM_CONNECT → UPDATE_SYNC_REQ → UPDATE_START_REQ (GOTO_NEXT_STATE) →
  UPDATE_IN_PROGRESS_RES → UPDATE_COMPLETE_IND → VM_DISCONNECT

Usage::

    import asyncio
    from benlink.firmware import fetch_firmware
    from benlink.firmware_updater import FirmwareUpdater
    from benlink.command import CommandConnection

    async def update_radio(mac: str, channel: int):
        # Fetch firmware from Benshikj OSS (layers 1+2)
        bundle = fetch_firmware(fw_version="V0.9.2-7")
        if bundle is None:
            print("No update available")
            return

        # Phase 1 — transfer
        async with CommandConnection.new_rfcomm(mac, channel) as conn:
            updater = FirmwareUpdater(conn, bundle,
                                      progress_cb=lambda s, d, t: print(f"{s} {d}/{t}"))
            await updater.transfer()
            # Radio reboots here; RFCOMM connection will drop shortly after

        print("Transfer complete — waiting for radio to reboot…")
        await asyncio.sleep(20)

        # Phase 2 — confirm (fresh connection)
        async with CommandConnection.new_rfcomm(mac, channel) as conn:
            await FirmwareUpdater.confirm(conn, bundle)

        print("Firmware update complete!")

    asyncio.run(update_radio("38:D2:00:00:F7:F5", channel=1))

Notes
-----
- Uses the existing RFCOMM command connection (same channel as normal radio comms).
  The VM channel UUID 00001107-D102-11E1-9B23-00025B00A5A5 is the GAIA VM RFCOMM
  *service* UUID used for SDP discovery; the actual communication goes over the
  already-connected GAIA command channel.
- Chunk size is device-driven via UPDATE_DATA_BYTES_REQ; no hard-coded 145-byte
  assumption is made.
- n_bytes_skip in UPDATE_DATA_BYTES_REQ supports mid-update resume; implemented
  defensively but not exercised in normal logs.
"""

from __future__ import annotations

import asyncio
import typing as t

from .firmware import FirmwareBundle, ProgressCallback
from .command import UnknownProtocolMessage

from .protocol.command.message import Message, CommandGroup, ExtendedCommand
from .protocol.command.common import ReplyStatus
from .protocol.command.bt_notification import BtEventNotificationBody, BtEventType
from .protocol.command.vm import (
    UpdateStartCfmCode,
    VmConnectBody,
    VmDisconnectBody,
    VmControlBody,
    VmControlType,
    VmuPacketType,
    VmControlUpdateSyncReq,
    VmControlUpdateStartReq,
    VmControlUpdateDataStartReq,
    VmControlUpdateData,
    VmControlUpdateIsValidationDoneReq,
    VmControlUpdateTransferCompleteRes,
    VmControlUpdateInProgressRes,
    VmControlUpdateAbortReq,
)

# ── Timeouts ──────────────────────────────────────────────────────────────────

_VM_REPLY_TIMEOUT: float = 15.0   # VM_CONNECT / VM_DISCONNECT reply
_VMU_TIMEOUT: float = 30.0        # General VMU_PACKET confirmation
_CHUNK_TIMEOUT: float = 60.0      # UPDATE_DATA_BYTES_REQ between chunks
_VALIDATION_TIMEOUT: float = 120.0  # UPDATE_TRANSFER_COMPLETE_IND (CRC check)
_COMPLETE_TIMEOUT: float = 120.0  # UPDATE_COMPLETE_IND after post-reboot confirm


# ── Low-level message builders ────────────────────────────────────────────────

def _msg_vm_connect() -> Message:
    return Message(
        command_group=CommandGroup.EXTENDED,
        is_reply=False,
        command=ExtendedCommand.VM_CONNECT,
        body=VmConnectBody(),
    )


def _msg_vm_disconnect() -> Message:
    return Message(
        command_group=CommandGroup.EXTENDED,
        is_reply=False,
        command=ExtendedCommand.VM_DISCONNECT,
        body=VmDisconnectBody(),
    )


def _msg_vm_control(
    ctrl_type: VmControlType,
    inner: t.Any,
    n_bytes_payload: int,
) -> Message:
    return Message(
        command_group=CommandGroup.EXTENDED,
        is_reply=False,
        command=ExtendedCommand.VM_CONTROL,
        body=VmControlBody(
            vm_control_type=ctrl_type,
            n_bytes_payload=n_bytes_payload,
            msg=inner,
        ),
    )


# ── Main class ────────────────────────────────────────────────────────────────

class FirmwareUpdater:
    """
    GAIA BT firmware delivery state machine (Layer 3).

    Accepts a ``CommandConnection`` (from :mod:`benlink.command`) that is
    already connected over RFCOMM.  VM_CONNECT / VM_CONTROL messages are sent
    over this same connection; VMU_PACKET replies arrive as
    ``BT_EVENT_NOTIFICATION`` events on the same channel.

    See module docstring for a complete usage example.
    """

    def __init__(
        self,
        conn: t.Any,   # benlink.command.CommandConnection; t.Any avoids bleak import
        bundle: FirmwareBundle,
        progress_cb: t.Optional[ProgressCallback] = None,
    ) -> None:
        self._conn = conn
        self._bundle = bundle
        self._progress_cb = progress_cb

    # ── Private transport helpers ─────────────────────────────────────────────

    async def _send(self, msg: Message) -> None:
        """Send a raw protocol Message via the underlying link."""
        await self._conn._link.send(msg)

    async def _wait_vm_reply(
        self,
        command: ExtendedCommand,
        timeout: float = _VM_REPLY_TIMEOUT,
    ) -> t.Any:
        """
        Wait for the ``is_reply=True`` acknowledgement for a VM extended command.

        Returns the parsed body object (e.g. ``VmConnectReplyBody``).
        Raises ``RuntimeError`` on timeout.
        """
        queue: asyncio.Queue[t.Any] = asyncio.Queue()

        def _handler(radio_msg: t.Any) -> None:
            if not isinstance(radio_msg, UnknownProtocolMessage):
                return
            proto = radio_msg.message
            if (
                proto.is_reply
                and proto.command_group == CommandGroup.EXTENDED
                and proto.command == command
            ):
                queue.put_nowait(proto.body)

        remove = self._conn._add_message_handler(_handler)
        try:
            return await asyncio.wait_for(queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            raise RuntimeError(
                f"Timed out ({timeout}s) waiting for {command.name} reply"
            )
        finally:
            remove()

    async def _wait_vmu(
        self,
        expected_type: VmuPacketType,
        timeout: float = _VMU_TIMEOUT,
    ) -> t.Any:
        """
        Wait for a ``BT_EVENT_NOTIFICATION / VMU_PACKET`` of ``expected_type``.

        Returns the inner ``msg`` object of the matching ``VmuPacket``
        (e.g. ``VmControlUpdateStartCfm``, ``VmControlUpdateDataBytesReq``).
        Raises ``RuntimeError`` on timeout.
        """
        queue: asyncio.Queue[t.Any] = asyncio.Queue()

        def _handler(radio_msg: t.Any) -> None:
            if not isinstance(radio_msg, UnknownProtocolMessage):
                return
            body = radio_msg.message.body
            if not isinstance(body, BtEventNotificationBody):
                return
            if body.bt_event_type != BtEventType.VMU_PACKET:
                return
            vmu = body.bt_event
            if vmu.vmu_packet_type == expected_type:
                queue.put_nowait(vmu.msg)

        remove = self._conn._add_message_handler(_handler)
        try:
            return await asyncio.wait_for(queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            raise RuntimeError(
                f"Timed out ({timeout}s) waiting for VMU {expected_type.name}"
            )
        finally:
            remove()

    # ── Protocol step helpers ─────────────────────────────────────────────────

    async def _step_vm_connect(self) -> None:
        await self._send(_msg_vm_connect())
        reply = await self._wait_vm_reply(ExtendedCommand.VM_CONNECT)
        if hasattr(reply, "status") and reply.status != ReplyStatus.SUCCESS:
            raise RuntimeError(f"VM_CONNECT rejected: {reply.status.name}")

    async def _step_vm_disconnect(self) -> None:
        await self._send(_msg_vm_disconnect())

    async def _step_sync(self, md5_tail: bytes) -> None:
        """Send UPDATE_SYNC_REQ; wait for UPDATE_SYNC_CFM."""
        await self._send(_msg_vm_control(
            VmControlType.UPDATE_SYNC_REQ,
            VmControlUpdateSyncReq(md5sum_tail=md5_tail),
            n_bytes_payload=4,
        ))
        await self._wait_vmu(VmuPacketType.UPDATE_SYNC_CFM)

    async def _step_start(self) -> UpdateStartCfmCode:
        """Send UPDATE_START_REQ; return cfm_code from UPDATE_START_CFM."""
        await self._send(_msg_vm_control(
            VmControlType.UPDATE_START_REQ,
            VmControlUpdateStartReq(),
            n_bytes_payload=0,
        ))
        cfm = await self._wait_vmu(VmuPacketType.UPDATE_START_CFM)
        return cfm.cfm_code

    async def _step_data_start(self) -> None:
        """Send UPDATE_DATA_START_REQ (no VMU reply; device follows with BYTES_REQ)."""
        await self._send(_msg_vm_control(
            VmControlType.UPDATE_START_DATA_REQ,
            VmControlUpdateDataStartReq(),
            n_bytes_payload=0,
        ))

    async def _step_abort(self) -> None:
        """Send UPDATE_ABORT_REQ (best-effort; no reply wait)."""
        try:
            await self._send(_msg_vm_control(
                VmControlType.UPDATE_ABORT_REQ,
                VmControlUpdateAbortReq(),
                n_bytes_payload=0,
            ))
        except Exception:
            pass

    # ── Public API ────────────────────────────────────────────────────────────

    async def transfer(self) -> None:
        """
        Phase 1: Transfer the firmware image to the radio.

        The method returns once the radio has acknowledged the complete
        transfer (``UPDATE_TRANSFER_COMPLETE_RES`` sent).  Shortly afterwards
        the radio will reboot and the BT connection will drop.

        Typical flow after calling this method:

        1. Disconnect / close the ``CommandConnection``.
        2. ``await asyncio.sleep(15)`` (or poll until BT reappears).
        3. Reconnect on the same RFCOMM channel.
        4. Call :meth:`confirm` on the new connection.

        Raises
        ------
        RuntimeError
            On any protocol error or timeout.
        """
        fw = self._bundle.data
        total = len(fw)
        md5_tail = self._bundle.md5_tail

        try:
            # ── Phase 1a: handshake ───────────────────────────────────────────
            await self._step_vm_connect()
            await self._step_sync(md5_tail)

            cfm_code = await self._step_start()
            if cfm_code == UpdateStartCfmCode.GOTO_NEXT_STATE:
                raise RuntimeError(
                    "UPDATE_START_CFM returned GOTO_NEXT_STATE before transfer. "
                    "The radio may already be partway through an update. "
                    "Power-cycle the radio and retry, or call confirm() if a "
                    "previous transfer completed."
                )

            # ── Phase 1b: data transfer (device-driven chunking) ──────────────
            await self._step_data_start()

            offset = 0
            while offset < total:
                req = await self._wait_vmu(
                    VmuPacketType.UPDATE_DATA_BYTES_REQ,
                    timeout=_CHUNK_TIMEOUT,
                )
                n = req.n_bytes_requested
                skip = req.n_bytes_skip   # non-zero only on resume
                offset += skip

                chunk = fw[offset: offset + n]
                if not chunk:
                    raise RuntimeError(
                        f"Device requested {n} bytes at offset {offset} "
                        f"but firmware is only {total} bytes"
                    )

                is_last = (offset + len(chunk) >= total)

                await self._send(_msg_vm_control(
                    VmControlType.UPDATE_DATA,
                    VmControlUpdateData(
                        is_final_fragment=is_last,
                        data=chunk,
                    ),
                    n_bytes_payload=1 + len(chunk),
                ))

                offset += len(chunk)

                if self._progress_cb:
                    self._progress_cb("flash", offset, total)

            # ── Phase 1c: validation & transfer-complete ──────────────────────
            await self._send(_msg_vm_control(
                VmControlType.UPDATE_IS_VALIDATION_DONE_REQ,
                VmControlUpdateIsValidationDoneReq(),
                n_bytes_payload=0,
            ))
            await self._wait_vmu(
                VmuPacketType.UPDATE_TRANSFER_COMPLETE_IND,
                timeout=_VALIDATION_TIMEOUT,
            )

            # Tell the radio the transfer is complete — it will now reboot
            await self._send(_msg_vm_control(
                VmControlType.UPDATE_TRANSFER_COMPLETE_RES,
                VmControlUpdateTransferCompleteRes(is_complete=True),
                n_bytes_payload=1,
            ))

        except Exception:
            await self._step_abort()
            raise

    @staticmethod
    async def confirm(
        conn: t.Any,       # CommandConnection (fresh, post-reboot)
        bundle: FirmwareBundle,
    ) -> None:
        """
        Phase 2: Confirm the completed update after the radio reboots.

        Call on a *new* ``CommandConnection`` after reconnecting post-reboot.
        The radio expects ``UPDATE_START_CFM`` to return ``GOTO_NEXT_STATE``
        at this point, indicating it is ready to finalise the update.

        Parameters
        ----------
        conn:
            A freshly connected ``CommandConnection`` (RFCOMM).
        bundle:
            The same ``FirmwareBundle`` used in :meth:`transfer`
            (needed for the md5_tail in UPDATE_SYNC_REQ).

        Raises
        ------
        RuntimeError
            On any protocol error or timeout.
        """
        updater = FirmwareUpdater(conn, bundle)

        await updater._step_vm_connect()
        await updater._step_sync(bundle.md5_tail)

        cfm_code = await updater._step_start()
        if cfm_code != UpdateStartCfmCode.GOTO_NEXT_STATE:
            raise RuntimeError(
                f"Expected GOTO_NEXT_STATE in post-reboot UPDATE_START_CFM, "
                f"got {cfm_code.name}. The radio may not have rebooted yet."
            )

        # Signal that the update is in progress (finalising)
        await updater._send(_msg_vm_control(
            VmControlType.UPDATE_IN_PROGRESS_RES,
            VmControlUpdateInProgressRes(),
            n_bytes_payload=1,
        ))

        # Wait for the radio to confirm the update is fully applied
        await updater._wait_vmu(
            VmuPacketType.UPDATE_COMPLETE_IND,
            timeout=_COMPLETE_TIMEOUT,
        )

        await updater._step_vm_disconnect()
