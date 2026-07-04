# benlink N76 Support — Testing Roadmap

Companion to [`docs/testing/N76.md`](docs/testing/N76.md). This file
tracks what still needs to be exercised on the Vero VR-N76 to fully validate
benlink support, prioritized so the highest-value / easiest-first work comes
first.

Status legend:
- ✅ verified working with the N76
- 🟡 code path exercised but not fully verified end-to-end
- 🔴 untested / not implemented

---

## Tier 1 — Basic operations already verified ✅

Ran successfully during the initial N76 bring-up session (2026-07-03):

- BLE connect via peripheral UUID (macOS)
- Read: `device_info`, `status`, `settings`, `battery_level`, all `channels`
- Write: `set_channel(...)` for name, RX/TX freq, CTCSS tones, bandwidth,
  scan flag, `tx_disable`. Round-trips + persists across power cycle.
- CSV bulk-programming via `examples/write_channels_csv.py`

Nothing action-required here — but any change to the `_pad`-tolerant
patches in `dev_info.py`, `status.py`, `rf_ch.py`, `phone_status.py`
needs a re-verification of at least the reads (they parse the affected
structs).

## Tier 2 — Immediately testable tomorrow 🟡

Low risk, no protocol changes needed, just exercise more of the existing
`RadioController` surface.

### 2.1 Battery + voltage reads
- `await radio.battery_voltage()` — is the mapping right on the N76?
  Compare against the on-screen indicator at three levels (full,
  mid, low-warning).
- `await radio.battery_level_as_percentage()`

### 2.2 Settings mutation
- `radio.settings` is a full `Settings` struct with 50+ fields. Try writing
  a subset via `radio.set_settings(...)` (if exposed) or by round-tripping
  through the raw command layer:
  - `imperial_unit` toggle
  - `mic_gain`
  - `squelch_level`
  - `screen_timeout`
  - `power_saving_mode`
  Confirm each takes effect on the device and survives a reboot.

### 2.3 Beacon (APRS) settings
- `BeaconSettings` / `BeaconSettingsArgs` exist in `command.py`. Read
  current beacon config from the radio.
- Attempt to write a new beacon config with a **placeholder** callsign
  (e.g. `TEST-1`), verify the radio accepts it. Do **not** actually
  transmit a beacon on a live APRS frequency during testing — put the
  radio on a dummy load or a non-APRS frequency.

### 2.4 Event handler / notifications
- Subscribe with `radio.add_event_handler(...)`, then wiggle knobs on
  the radio (change channel, turn scan on/off) and confirm events fire.
- Enumerate which `EventType` values actually come out of the N76 vs
  which are silent — helpful to document.

### 2.5 Bandwidth NARROW round-trip
- All the marine + GMRS entries in the example CSVs use NARROW. Verify
  after writing that `radio.channels[slot].bandwidth == "NARROW"` and
  that the radio's on-screen indicator matches. (Some clones lie about
  bandwidth — the N76 is not known to, but should be confirmed.)

## Tier 3 — Reverse-engineering targets 🔴

These need actual work (protocol tracing) beyond just poking benlink.

### 3.1 Regions / channel banks (highest user value)
The N76 UI calls them "groups" (up to 12), each with a 32-channel table
+ a name. Protocol enum already knows about them:

- `READ_REGION_NAME` (73)
- `WRITE_REGION_CH` (58)
- `WRITE_REGION_NAME` (59)
- `SET_REGION` (60)
- `Status.curr_region` (already parsed)

**No body structs exist yet** for any of these opcodes.

Suggested attack:

1. Sniff BLE traffic while the HT app switches regions & reads a
   region's channel table. `btsnoop_hci.log` on Android is the easiest
   capture path. Notes on wire format in
   [`btsnoop/`](btsnoop/) of this repo.
2. Guess: `WRITE_REGION_CH` body is probably `<region_id: u8><RfCh>`.
3. Implement `region.py` with `SetRegionBody`, `ReadRegionNameBody`,
   `WriteRegionNameBody`, `ReadRegionChBody`, `WriteRegionChBody` +
   their `*ReplyBody` counterparts.
4. Add `RadioController.regions: list[Region]` state + `set_region()` +
   `set_region_channel()` + `get_region_channels()` methods.

If this lands, the CSV-writer example can grow a `--region <n>` flag
and stop requiring the user to switch groups on the device first.

### 3.2 DevInfo undocumented bits
Currently `_pad: int = bf_int(2, default=0)` on N76. Some bits are set
in the field. Sniffing the HT app talking to the same device would
show whether Vero's app reads them; if so, decompiling
`com.benshi.htmate` (or Vero's rebrand) would map them to feature flags.
Not urgent — parse works fine now.

### 3.3 KISS TNC mode
`Settings.kiss_en` and `Settings.kiss_upload_tx_msg` exist. The N76 can
run as a Bluetooth KISS TNC (per BTech/Radioddity's public firmware
notes). Need to confirm:
- Does flipping `kiss_en=True` via `set_settings` actually enable it?
- Does that expose a KISS stream over the existing BLE / RFCOMM channel,
  or on a separate profile?
- Can `TncDataFragment` frames be received/sent while KISS mode is on?

### 3.4 Firmware version reporting
`device_info` exposes `hw_ver` and `soft_ver` as raw ints. The Vero HT
app maps these to human-readable strings (e.g. "0.7.1"). Figure out the
mapping (probably major.minor.patch nibbles) and add a helper.

### 3.5 Audio TX/RX
Author flagged in the README that audio is awkward pending libsbc
bindings. Confirmed audio bytes come out of the N76 during RX with
squelch open (based on `bt-ht-n76` prior art), but decoding needs pyav
or libsbc. Out of scope for a single evening; parking here.

### 3.6 Firmware update path
Issue #10 in the upstream repo asks for firmware flashing over BLE.
Not attempting this on the N76 — the risk/reward is bad while the HT
app still works and can flash. Revisit only if Vero stops maintaining
the app.

## Tier 4 — Nice-to-haves

- Windows validation (bleak works, but nobody's confirmed on the N76 there).
- Linux validation, especially RFCOMM path (the auto-channel discovery
  gap in [#9](https://github.com/khusmann/benlink/issues/9) still bites).
- A little TUI (`benlink-cli`?) that wraps `RadioController` for
  interactive use — read status, dump channels, load a CSV, etc.

## Not doing (explicitly out of scope)

- **Region switching from the client library.** Deferred; use the radio's
  hardware button (`PREV_REGION`/`NEXT_REGION` PF-key functions) until 3.1
  lands.
- **Modifying anything about the HT app or Vero's cloud services.** benlink
  is offline-only and should stay that way.

---

**Contribution note:** If you own an N76 and are testing any of the Tier 2
or Tier 3 items, please open an issue with your firmware version, the
struct you exercised, and the raw bytes if you have them. That's how we
close the gap on the strict-`_pad` fields most reliably.
