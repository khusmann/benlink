"""Delivering an assembled firmware image to a radio.

**Not implemented yet** ([issue #10](https://github.com/khusmann/benlink/issues/10)).

The message types are in `benlink.protocol.command.vm`; what remains is the state
machine that drives them. The transfer runs over the same command connection as
everything else, in two phases separated by a reboot:

    VM_CONNECT
    UPDATE_SYNC_REQ          -> UPDATE_SYNC_CFM
    UPDATE_START_REQ         -> UPDATE_START_CFM
    UPDATE_START_DATA_REQ
    UPDATE_DATA              <- UPDATE_DATA_BYTES_REQ   (repeats)
    UPDATE_IS_VALIDATION_DONE_REQ
                             -> UPDATE_TRANSFER_COMPLETE_IND
    UPDATE_TRANSFER_COMPLETE_RES

    [radio reboots, connection drops, reconnect]

    VM_CONNECT
    UPDATE_SYNC_REQ          -> UPDATE_SYNC_CFM
    UPDATE_START_REQ         -> UPDATE_START_CFM
    UPDATE_IN_PROGRESS_RES   -> UPDATE_COMPLETE_IND
    VM_DISCONNECT

Two things to get right when this is built:

- `UPDATE_SYNC_CFM` reports the radio's `UpdateState`, so which phase to run should
  be decided from what the radio says rather than tracked locally. That also covers
  resuming an interrupted transfer.
- The chunk loop is driven by `UPDATE_DATA_BYTES_REQ`, so the subscription has to be
  established before the request that triggers it and held for the whole transfer.
  Registering per chunk drops packets.

The commit and reboot behaviour at the end of phase one is not settled, and differs
between models.
"""

from __future__ import annotations
import typing as t

from ._fetch import FirmwareBundle, ProgressCallback

if t.TYPE_CHECKING:
    from ..command import CommandConnection


async def flash(
    conn: CommandConnection,
    bundle: FirmwareBundle,
    progress: ProgressCallback | None = None,
) -> None:
    """Deliver an assembled firmware image to a connected radio.

    Not implemented. See the module docstring for the protocol.
    """
    raise NotImplementedError(
        "flashing is not implemented yet: "
        "https://github.com/khusmann/benlink/issues/10"
    )
