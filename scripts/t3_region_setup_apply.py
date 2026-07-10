#!/usr/bin/env python3
"""Tier 3 — region setup applier for Eric's N76.

Renames regions 0/2/3/4/5, rebuilds regions 0 (Ham) and 3 (Hull Scan),
clones region 1 slot 32 (APRS) into all other regions' slot 32.

Every existing channel that will be overwritten is backed up to a JSON
file before the write. --dry-run prints the write plan without touching
the radio. --rollback restores from the last backup.

Usage:
    python t3_region_setup_apply.py --dry-run   # print plan
    python t3_region_setup_apply.py --apply     # execute
    python t3_region_setup_apply.py --rollback  # restore last backup
"""
from __future__ import annotations
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from bleak import BleakScanner
import benlink.controller as bc
from benlink.command import Channel

sys.path.insert(0, str(Path(__file__).parent))
try:
    from _teelog import setup_teelog
    setup_teelog(__file__)
except ImportError:
    # Local dev / dry-run outside the Air workspace.
    pass

BACKUP_DIR = Path.home() / "src" / "n76" / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Region rename plan
# ---------------------------------------------------------------------------
RENAMES: dict[int, str] = {
    0: "Ham",
    # region 1 stays "Family Ops" -- skipped
    2: "Weather",
    3: "Hull Scan",
    4: "Marine",
    5: "GMRS",
}

# ---------------------------------------------------------------------------
# Rebuild specs. Each entry is (name, rx_mhz, tx_mhz, bw, tone, scan, tx_disable, mute)
#   tone: None | float(PL) | ("D", n_int)   -- DCS as ("D", n)
#   bw: "WIDE" | "NARROW"
# ---------------------------------------------------------------------------
Tone = float | tuple | None  # PL Hz | ("D", int) DCS | None

def _t(pl_or_dcs):
    """Tone helper. Pass float PL Hz, int for DCS, or None."""
    return pl_or_dcs

# Region 0: Ham (South Shore MA) — 15 defined slots
HAM_SLOTS: list[tuple[int, str, float, float, str, Tone, bool, bool, bool]] = [
    # slot, name, rx, tx, bw, tone (both), scan, tx_disable, mute
    ( 1, "2m Call",   146.520, 146.520, "WIDE", None,   True,  False, False),
    ( 2, "70cm Call", 446.000, 446.000, "WIDE", None,   True,  False, False),
    ( 3, "Weymouth",  147.345, 147.945, "WIDE", 110.9,  True,  False, False),
    ( 4, "Marshfld",  145.390, 144.790, "WIDE",  67.0,  True,  False, False),
    ( 5, "Plym 685",  146.685, 146.085, "WIDE", 131.8,  True,  False, False),
    ( 6, "Plym 315",  147.315, 147.915, "WIDE",  67.0,  True,  False, False),
    ( 7, "Bridgewtr", 147.180, 147.780, "WIDE",  67.0,  True,  False, False),
    ( 8, "BARC 230",  145.230, 144.630, "WIDE",  88.5,  True,  False, False),
    ( 9, "Sharon",    146.865, 146.265, "WIDE", 103.5,  True,  False, False),
    (10, "Norwood",   147.210, 147.810, "WIDE", 100.0,  True,  False, False),
    (11, "Falmouth",  147.375, 147.975, "WIDE", 110.9,  True,  False, False),
    (12, "Whitman",   147.225, 147.825, "WIDE",  67.0,  True,  False, False),
    (13, "W Bridge",  146.775, 146.175, "WIDE", ("D",244), True, False, False),
    (14, "Fall Rvr",  146.805, 146.205, "WIDE",  67.0,  True,  False, False),
    (15, "Dartmouth", 147.000, 147.600, "WIDE",  67.0,  True,  False, False),
]
HAM_BLANK = list(range(16, 32))  # slots 16..31 blanked (32 = APRS clone)

# Region 3: Hull Scan (convenience mash-up) — 25 defined slots
HULL_SLOTS: list[tuple[int, str, float, float, str, Tone, bool, bool, bool]] = [
    # slot, name, rx, tx, bw, tone, scan, tx_disable, mute
    ( 1, "2m Call",   146.520, 146.520, "WIDE",   None,  True,  False, False),
    ( 2, "70cm Call", 446.000, 446.000, "WIDE",   None,  True,  False, False),
    ( 3, "SS Local",  147.420, 147.420, "WIDE",   None,  True,  False, False),
    ( 4, "Weymouth",  147.345, 147.945, "WIDE",  110.9,  True,  False, False),
    ( 5, "Marshfld",  145.390, 144.790, "WIDE",   67.0,  True,  False, False),
    ( 6, "Mar16 Dst", 156.800, 156.800, "NARROW", None,  True,  True,  False),  # rx-only distress
    ( 7, "Mar09 Hai", 156.450, 156.450, "NARROW", None,  True,  False, False),
    ( 8, "Mar68 Rec", 156.425, 156.425, "WIDE",   None,  True,  False, False),
    ( 9, "Mar72 Rec", 156.625, 156.625, "NARROW", None,  True,  False, False),
    (10, "MURS 1",    151.820, 151.820, "NARROW", None,  True,  False, False),
    (11, "MURS 2",    151.880, 151.880, "NARROW", None,  True,  False, False),
    (12, "MURS 3",    151.940, 151.940, "NARROW", None,  True,  False, False),
    (13, "MURS Blue", 154.570, 154.570, "WIDE",   None,  True,  False, False),
    (14, "MURS Grn",  154.600, 154.600, "WIDE",   None,  True,  False, False),
    (15, "GMRS 15",   462.550, 462.550, "NARROW", None,  True,  False, False),
    (16, "GMRS 16",   462.575, 462.575, "NARROW", None,  True,  False, False),
    (17, "GMRS 17",   462.600, 462.600, "NARROW", None,  True,  False, False),
    (18, "GMRS 18",   462.625, 462.625, "NARROW", None,  True,  False, False),
    (19, "GMRS 19",   462.650, 462.650, "NARROW", None,  True,  False, False),
    (20, "GMRS 20",   462.675, 462.675, "NARROW", None,  True,  False, False),
    (21, "GMRS 21",   462.700, 462.700, "NARROW", None,  True,  False, False),
    (22, "GMRS 22",   462.725, 462.725, "NARROW", None,  True,  False, False),
    (23, "Quin 550",  462.550, 467.550, "NARROW", 141.3, True,  False, False),
    (24, "WX Boston", 162.475, 162.475, "WIDE",   None,  True,  True,  False),  # rx-only
    (25, "WX Plymth", 162.400, 162.400, "WIDE",   None,  True,  True,  False),  # rx-only
]
HULL_BLANK = list(range(26, 32))  # slots 26..31 blanked, 32 = APRS clone


# ---------------------------------------------------------------------------
# Channel construction
# ---------------------------------------------------------------------------
def _tone_to_field(tone: Tone):
    """Convert plan-file tone into benlink Channel field value."""
    if tone is None:
        return None
    if isinstance(tone, tuple) and tone[0] == "D":
        from benlink.command import DCS
        return DCS(n=int(tone[1]))
    return float(tone)


def build_channel(slot_idx: int, name: str, rx: float, tx: float,
                  bw: str, tone: Tone, scan: bool,
                  tx_disable: bool, mute: bool) -> Channel:
    """Build a fully-specified Channel from a plan tuple.

    Uses safe defaults for the fields we don't set per-slot (modulation
    FM, no talk-around, max power, no fixed-* flags).
    """
    t = _tone_to_field(tone)
    return Channel(
        channel_id=slot_idx - 1,  # radio uses 0-based
        tx_mod="FM",
        tx_freq=tx,
        rx_mod="FM",
        rx_freq=rx,
        tx_sub_audio=t,
        rx_sub_audio=t,
        scan=scan,
        tx_at_max_power=True,
        talk_around=False,
        bandwidth=bw,
        pre_de_emph_bypass=False,
        sign=False,
        tx_at_med_power=False,
        tx_disable=tx_disable,
        fixed_freq=False,
        fixed_bandwidth=False,
        fixed_tx_power=False,
        mute=mute,
        name=name,
    )


def blank_channel(slot_idx: int) -> Channel:
    """A cleared channel slot -- zero freqs, empty name."""
    return Channel(
        channel_id=slot_idx - 1,
        tx_mod="FM",
        tx_freq=0.0,
        rx_mod="FM",
        rx_freq=0.0,
        tx_sub_audio=None,
        rx_sub_audio=None,
        scan=False,
        tx_at_max_power=True,
        talk_around=False,
        bandwidth="WIDE",
        pre_de_emph_bypass=False,
        sign=False,
        tx_at_med_power=False,
        tx_disable=False,
        fixed_freq=False,
        fixed_bandwidth=False,
        fixed_tx_power=False,
        mute=False,
        name="",
    )


# ---------------------------------------------------------------------------
# Radio interaction
# ---------------------------------------------------------------------------
async def find_radio(timeout: float = 12.0) -> str:
    print(f"scanning {timeout}s for VR-N76...")
    devices = await BleakScanner.discover(timeout=timeout)
    for d in devices:
        if d.name and "VR-N76" in d.name.upper():
            print(f"  found {d.name!r} @ {d.address}")
            return d.address
    raise RuntimeError("N76 not found")


def channel_to_dict(ch: Channel) -> dict:
    """Serialize Channel for JSON backup."""
    d = ch.model_dump()
    # Sub-audio may be a DCS instance
    for k in ("tx_sub_audio", "rx_sub_audio"):
        v = d.get(k)
        if hasattr(v, "n"):
            d[k] = {"__dcs__": v.n}
    return d


def dict_to_channel(d: dict) -> Channel:
    d = dict(d)
    from benlink.command import DCS
    for k in ("tx_sub_audio", "rx_sub_audio"):
        v = d.get(k)
        if isinstance(v, dict) and "__dcs__" in v:
            d[k] = DCS(n=v["__dcs__"])
    return Channel(**d)


async def read_all_regions(radio) -> dict[int, dict[int, dict]]:
    """Read every channel of every region for backup.

    Returns {region_id: {channel_id: channel_dict}} — channel_id is 0-based.
    """
    saved_region = radio.status.curr_region
    snapshot: dict[int, dict[int, dict]] = {}
    for r_idx in range(len(radio.region_names)):
        if r_idx != radio.status.curr_region:
            await radio.set_region(r_idx)
        region_snap: dict[int, dict] = {}
        for i in range(radio.device_info.channel_count):
            ch = radio.channels[i]
            region_snap[i] = channel_to_dict(ch)
        snapshot[r_idx] = region_snap
        print(f"  backed up region {r_idx} ({radio.region_names[r_idx]!r}): {radio.device_info.channel_count} slots")
    # restore active region
    if radio.status.curr_region != saved_region:
        await radio.set_region(saved_region)
    return snapshot


def save_backup(snapshot: dict, region_names: list[str]) -> Path:
    ts = time.strftime("%Y%m%d-%H%M%S")
    path = BACKUP_DIR / f"n76-full-backup-{ts}.json"
    payload = {
        "timestamp": ts,
        "region_names": region_names,
        "regions": {
            str(r): {str(c): v for c, v in ch.items()}
            for r, ch in snapshot.items()
        },
    }
    path.write_text(json.dumps(payload, indent=2))
    print(f"backup saved → {path}")
    return path


def latest_backup() -> Path | None:
    files = sorted(BACKUP_DIR.glob("n76-full-backup-*.json"))
    return files[-1] if files else None


def print_write_plan(aprs_template: Channel) -> None:
    print("\n=== APRS template (from region 1 slot 32) ===")
    print(f"  name={aprs_template.name!r} rx={aprs_template.rx_freq} tx={aprs_template.tx_freq}")
    print(f"  bw={aprs_template.bandwidth} tone={aprs_template.tx_sub_audio}")
    print(f"  mute={aprs_template.mute} scan={aprs_template.scan} tx_disable={aprs_template.tx_disable}")

    print("\n=== Region renames ===")
    for r_idx, new in RENAMES.items():
        print(f"  region {r_idx}: → {new!r}")

    print("\n=== APRS slot-32 clones ===")
    for r_idx in [0, 2, 3, 4, 5]:
        print(f"  region {r_idx} slot 32 ← APRS clone")

    print("\n=== Region 0 rebuild (Ham) ===")
    for slot, name, rx, tx, bw, tone, scan, txd, mute in HAM_SLOTS:
        print(f"  slot {slot:>2}: {name:<10} rx={rx:>8.3f} tx={tx:>8.3f} {bw:<6} tone={tone} scan={scan} txdis={txd} mute={mute}")
    print(f"  slots {HAM_BLANK[0]}..{HAM_BLANK[-1]}: BLANKED")

    print("\n=== Region 3 rebuild (Hull Scan) ===")
    for slot, name, rx, tx, bw, tone, scan, txd, mute in HULL_SLOTS:
        print(f"  slot {slot:>2}: {name:<10} rx={rx:>8.3f} tx={tx:>8.3f} {bw:<6} tone={tone} scan={scan} txdis={txd} mute={mute}")
    print(f"  slots {HULL_BLANK[0]}..{HULL_BLANK[-1]}: BLANKED")

    total = len(RENAMES) + 5 + len(HAM_SLOTS) + len(HAM_BLANK) + len(HULL_SLOTS) + len(HULL_BLANK)
    print(f"\nTOTAL WRITES: {total}")


async def apply_writes(radio, aprs_template: Channel, dry_run: bool) -> None:
    conn = radio._conn

    async def write_channel_raw(region_id: int, ch: Channel):
        if dry_run:
            print(f"  DRY: write region {region_id} slot {ch.channel_id+1}: {ch.name!r}")
            return
        await conn.write_region_channel(region_id, ch)

    # 1) Renames
    print("\n--- renames ---")
    for r_idx, new in RENAMES.items():
        if dry_run:
            print(f"  DRY: rename region {r_idx} → {new!r}")
        else:
            await radio.set_region_name(r_idx, new)
            print(f"  region {r_idx} → {new!r}")

    # 2) APRS clones (regions 0, 2, 3, 4, 5 -- skip region 1 which is already correct)
    print("\n--- APRS slot-32 clones ---")
    for r_idx in [0, 2, 3, 4, 5]:
        aprs = aprs_template.model_copy(update={"channel_id": 31})
        await write_channel_raw(r_idx, aprs)
        if not dry_run:
            print(f"  region {r_idx} slot 32 ← APRS ({aprs.name!r})")

    # 3) Region 0 rebuild (Ham)
    print("\n--- region 0 rebuild (Ham) ---")
    for spec in HAM_SLOTS:
        slot, name, rx, tx, bw, tone, scan, txd, mute = spec
        ch = build_channel(slot, name, rx, tx, bw, tone, scan, txd, mute)
        await write_channel_raw(0, ch)
    for slot in HAM_BLANK:
        ch = blank_channel(slot)
        await write_channel_raw(0, ch)

    # 4) Region 3 rebuild (Hull Scan)
    print("\n--- region 3 rebuild (Hull Scan) ---")
    for spec in HULL_SLOTS:
        slot, name, rx, tx, bw, tone, scan, txd, mute = spec
        ch = build_channel(slot, name, rx, tx, bw, tone, scan, txd, mute)
        await write_channel_raw(3, ch)
    for slot in HULL_BLANK:
        ch = blank_channel(slot)
        await write_channel_raw(3, ch)

    print("\ndone.")


async def rollback(radio, backup_path: Path) -> None:
    conn = radio._conn
    data = json.loads(backup_path.read_text())
    saved_names = data["region_names"]

    # Restore names
    print("\n--- restore names ---")
    for r_idx, name in enumerate(saved_names):
        try:
            await radio.set_region_name(r_idx, name)
            print(f"  region {r_idx} → {name!r}")
        except Exception as e:
            print(f"  region {r_idx} restore-name FAILED: {e!r}")

    # Restore channels
    print("\n--- restore channels ---")
    for r_str, chans in data["regions"].items():
        r_idx = int(r_str)
        print(f"restoring region {r_idx}...")
        for c_str, cdict in chans.items():
            ch = dict_to_channel(cdict)
            await conn.write_region_channel(r_idx, ch)
        print(f"  region {r_idx}: {len(chans)} slots restored")

    print("\nrollback complete.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="print plan, don't touch radio")
    g.add_argument("--apply",   action="store_true", help="execute writes (backs up first)")
    g.add_argument("--rollback", action="store_true", help="restore latest backup")
    args = ap.parse_args()

    if args.dry_run:
        # Dry-run doesn't touch the radio. Print the plan using a synthetic
        # APRS template (matches Eric's actual region-1-slot-32 config).
        aprs_template = Channel(
            channel_id=31,
            tx_mod="FM", tx_freq=144.390,
            rx_mod="FM", rx_freq=144.390,
            tx_sub_audio=None, rx_sub_audio=None,
            scan=False,
            tx_at_max_power=True, talk_around=False,
            bandwidth="WIDE",
            pre_de_emph_bypass=False, sign=False,
            tx_at_med_power=False, tx_disable=False,
            fixed_freq=False, fixed_bandwidth=False, fixed_tx_power=False,
            mute=True,
            name="APRS",
        )
        print_write_plan(aprs_template)
        return

    address = await find_radio()
    async with bc.RadioController.new_ble(address) as radio:
        print(f"connected fw={radio.device_info.firmware_version}")
        print(f"current region: {radio.status.curr_region}")
        print(f"region names: {radio.region_names}\n")

        if args.rollback:
            bpath = latest_backup()
            if not bpath:
                print("no backup found in", BACKUP_DIR)
                return
            print(f"restoring from {bpath}...")
            await rollback(radio, bpath)
            return

        # Grab APRS template from region 1 slot 32
        saved = radio.status.curr_region
        if saved != 1:
            await radio.set_region(1)
        aprs_template = radio.channels[31]
        if saved != 1:
            await radio.set_region(saved)
        assert abs(aprs_template.rx_freq - 144.390) < 0.001 or args.dry_run, \
            f"unexpected APRS template freq {aprs_template.rx_freq}"

        print_write_plan(aprs_template)

        # --apply: back up first
        print("\n=== BACKING UP ===")
        snapshot = await read_all_regions(radio)
        save_backup(snapshot, list(radio.region_names))

        print("\n=== APPLYING WRITES ===")
        await apply_writes(radio, aprs_template, dry_run=False)


if __name__ == "__main__":
    asyncio.run(main())
