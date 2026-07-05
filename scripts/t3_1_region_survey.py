#!/usr/bin/env python3
"""Survey — dump names + all 32 channels for every region we have."""
import asyncio, sys
from pathlib import Path
from bleak import BleakScanner
import benlink.controller as bc

sys.path.insert(0, str(Path(__file__).parent))
from _teelog import setup_teelog
setup_teelog(__file__)


async def find_radio(timeout: float = 12.0) -> str:
    print(f"scanning {timeout}s for VR-N76...")
    devices = await BleakScanner.discover(timeout=timeout)
    for d in devices:
        if d.name and "VR-N76" in d.name.upper():
            print(f"  found {d.name!r} @ {d.address}")
            return d.address
    raise RuntimeError("N76 not found")


async def main() -> None:
    address = await find_radio()
    async with bc.RadioController.new_ble(address) as radio:
        print(f"connected fw={radio.device_info.firmware_version}")
        print(f"currently on region {radio.status.curr_region}")
        print(f"region names: {radio.region_names}\n")

        curr = radio.status.curr_region
        for r_idx, name in enumerate(radio.region_names):
            if r_idx != curr:
                await radio.set_region(r_idx)
            print(f"=== region {r_idx}: {name!r} ===")
            for i, ch in enumerate(radio.channels):
                # Only print channels with a name OR non-default freq
                name_str = getattr(ch, "name", "")
                rx = ch.rx_freq  # already in MHz (float)
                tx = ch.tx_freq
                bw = getattr(ch, "bandwidth", "?")
                tx_sub = getattr(ch, "tx_sub_audio", None)
                rx_sub = getattr(ch, "rx_sub_audio", None)
                mute = getattr(ch, "mute", None)
                scan = getattr(ch, "scan", None)
                tx_disable = getattr(ch, "tx_disable", None)
                if name_str or rx != 0 or tx != 0:
                    print(f"  ch{i+1:>2}: name={name_str!r:<14} rx={rx:>9.4f} tx={tx:>9.4f} bw={bw:<6} txT={tx_sub!r:<6} rxT={rx_sub!r:<6} mute={mute} scan={scan} txdis={tx_disable}")
            print()

        # Restore original region
        if radio.status.curr_region != curr:
            await radio.set_region(curr)
        print(f"restored to region {curr}")


if __name__ == "__main__":
    asyncio.run(main())
