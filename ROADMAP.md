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

### 2.3 Beacon (APRS) settings ✅ (read + write verified 2026-07-04)
- Read: `radio.beacon_settings` populates cleanly on connect. Full
  21-field dump via `scripts/t2_3_beacon_read.py`. Verified on N76
  fw=147 with `smart_beacon_en`, `smart_beacon_min/max_interval`,
  `mic_e_en`, and `send_id_by_aprs` exposed after the follow-up in
  3.5.b landed.
- Write: `scripts/t2_3b_beacon_write.py` toggles `should_share_location`
  False↔True and verifies (a) only the target field changes on the
  wire and in the cached state, (b) full baseline is restored after
  the round-trip. Passed clean on N76 fw=147; no adjacent-field
  damage. This confirms `set_beacon_settings(**kwargs)` is a
  targeted write like `set_settings(**kwargs)`.
- Placeholder-callsign write test on a safe (non-APRS) frequency
  still worth doing if we ever change `aprs_callsign` / `aprs_ssid` /
  `beacon_message`, but for the low-risk boolean case the API is
  proven safe.

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

**Reading the current region works today** — verified 2026-07-04 by
switching groups on the N76 and watching `HT_STATUS_CHANGED` payloads.
`curr_region` is 0-based (radio UI shows 1-based). Switching from Group
1→3→6→1→2→3 emitted `curr_region` 0→2→5→0→1→2 in that order.

**Also observed 2026-07-04:** every group switch also fires
`HT_SETTINGS_CHANGED` with the group's own `channel_a` / `channel_b`
values (settings appear region-scoped). `HT_CH_CHANGED` does **not**
fire on region switch — so `radio.channels[]` cache does not
auto-refresh when the region changes.

**✅ SET_REGION decoded and wired 2026-07-04.** Confirmed on N76 fw=147
via `scripts/t3_1_set_region_probe.py`:
- Request body: 1 byte `region_id` (0-based).
- Reply body: 1 byte `reply_status` (0 = SUCCESS).
- Probe: 3→0 flipped `curr_region` cleanly and the 32-slot channel
  table differed at every position (baseline had 32 named ham/APRS
  channels, region 0 had 10 named FRS/GMRS channels + empty slots).
  Restore back to 3 was bit-exact (0/32 slots drifted).
- Wired: `protocol/command/region.py` (SetRegionBody / SetRegionReplyBody),
  `SetRegion` / `SetRegionReply` in `command.py`, `radio.set_region(id)`
  on the controller. `set_region()` also re-reads `status` and the full
  `channels[]` table into the cache so the API stays coherent.

**✅ READ_REGION_NAME decoded and wired 2026-07-04.** Confirmed on N76
fw=147 via `scripts/t3_1_read_region_name_probe.py`:
- Request body: 1 byte `region_id`.
- Reply body on success (12 bytes): `<reply_status: u8=0><region_id: u8><name: str(10)>`,
  name null-padded fixed width.
- Reply body on out-of-range (1 byte): `<reply_status: u8=5=INVALID_PARAMETER>`.
- Wired the dynamic reply discriminator in `protocol/command/region.py`.
- New API: `radio.get_region_name(id)` (returns str or None if
  out-of-range) and `radio.get_region_names()` (auto-probes 0..N,
  stops at first INVALID_PARAMETER).

**Real-world regions on Eric's N76** (2026-07-04): 6 regions exist,
names 'NOAA Weath', 'Family Ops', 'NOAA Weath', '', '', ''. Regions
6..11 return INVALID_PARAMETER. So the enum's implicit "up to 12"
assumption was wrong — the N76 has 6 groups, not 12.

**✅ WRITE_REGION_NAME decoded and wired 2026-07-04.** Confirmed on N76
fw=147 via `scripts/t3_1_write_region_name_probe.py`:
- Request body: 11 bytes = `<region_id: u8><name: str(10)>`
- Reply body: 1 byte = `<reply_status>` (0 = SUCCESS)
- Round-trip on blank region 5: 'BENLINK' → read-back → restore → ''
- New API: `radio.set_region_name(region_id, name)`

**✅ WRITE_REGION_CH decoded and wired 2026-07-04.** Confirmed on N76
fw=147 via `scripts/t3_1_write_region_ch_probe.py`:
- Request body: 26 bytes = `<region_id: u8><RfCh (25 bytes)>`
- Reply body: 3 bytes = `<reply_status><region_id><channel_id>`
  (radio echoes both region_id and channel_id — nice defense-in-depth)
- Round-trip on region 5 slot 31: 'Quin 550' baseline → write 'TEST31'
  → verify → restore 'Quin 550' → verify. Bit-exact both ways.
- New API: `radio.set_region_channel(region_id, channel_id, **channel_args)`.
  Analogous to `set_channel()` but targets an arbitrary region, not
  just the currently-active one. Cache updates in-place if the target
  region is the current one; otherwise remains stale until the next
  region switch (which triggers a full channels[] refresh).

**Tier 3.1 is now complete on the read side and mostly complete on the
write side.** Remaining nice-to-haves:
- Auto-discover N regions at connect time and cache their names
  (currently `get_region_names()` probes on demand)
- Add a hydrator that reads all N region tables into memory on connect
  (would enable a `channels_in_region(region_id)` accessor without
  requiring a region switch)
- Confirm `WRITE_REGION_CH` into a *foreign* region survives a
  reboot (only round-trip has been verified; long-term persistence
  is very likely but worth checking on next power cycle)

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

### 3.5 Event payload decode gaps (raw samples captured 2026-07-04)

During Tier 2.4 testing on N76 (fw 147), these `EventNotification` events
fire but their bodies fall through to `UnknownEvent(data=...)`. Adding
real `Bitfield` types is straightforward once we have a few more samples.

**3.5.a `RADIO_STATUS_CHANGED` (event_type=8)**
- Observed body: 4 bytes, e.g. `00 00 00 00`
- Probably a status bitmask (screen mode / PTT / squelch flags). Need
  correlated capture: change one thing at a time on the radio and log
  which byte/bit flips.
- Capture script: `scripts/t3_5a_radio_status_capture.py`. Subscribes
  to RADIO_STATUS_CHANGED + HT_STATUS_CHANGED, prints each body with
  timestamp + bit-level diff vs previous, plus summary of distinct
  payloads. Ideal correlation source: watch TX bits flip while an
  auto-beacon fires.
- Timing gotcha: smart-beacon interval is not fixed. On the N76,
  `smart_beacon_min_interval` is the fast-moving cadence and
  `smart_beacon_max_interval` is the stationary cap (up to 30 min).
  Auto-beacon might not fire inside a short capture window if the
  radio is sitting still. For a guaranteed TX inside the window,
  either disable smart_beacon_en (fixed `location_share_interval`
  applies) or wait long enough for the stationary cap.

**3.5.c `POSITION_CHANGE` / `POSITION_CHANGED` (event_type=13) — seen firing but body not decoded**

When `should_share_location=True` and the N76 has a GPS fix, this event
fires every ~1s with an 18-byte body. Sample from 2026-07-04 (radio
stationary on m2uehlair):
```
13 5d 37 df 8d 24 00 07 00 00 00 a7 6a 49 16 8c 00 06
13 5d 37 df 8d 24 00 07 00 00 00 a7 6a 49 16 8d 00 06
13 5d 37 df 8d 24 00 07 00 00 00 a7 6a 49 16 8e 00 06
...
13 5d 37 df 8d 24 00 08 00 00 00 a7 6a 49 16 a9 00 06
```
- Bytes 0-3: `13 5d 37 df` constant — could be a GPS timestamp base
  (0xdf375d13 LE = 3745577747 = 2088-09-... probably GPS week seconds
  from a fixed epoch) or a session id.
- Byte 4: `8d` constant (radio was stationary; would probably encode
  something like speed / fix-quality on movement)
- Bytes 4-5: `8d 24` — constant. Possibly heading + something.
- Bytes 6-7: `00 07` observed for the first ~30s, then `00 08` for
  the rest. Number of visible sats climbed 7→8.
- Bytes 8-10: `00 00 00` constant.
- Bytes 11-14: `a7 6a 49 16` constant (stationary radio in Boston). If
  interpreted as int32 little-endian, `0x16496aa7 = 374,548,647`.
  In degrees×10^7 that's 37.4548647° — doesn't match Boston (42.36°N,
  -71.06°W). Might be lon (−71.0648° = −710648333 →
  0xD5A94DBB… doesn't match either). Encoding is not straight int32
  ×10^7; possibly Locus / Maidenhead-style packed, or a coord
  reference frame we haven't figured out.
- Byte 15: monotonic 1-byte counter (0x86 → 0xB6 across 48s, wraps at
  0xFF presumably). Ticks ~once per second, matches the event rate.
- Bytes 16-17: `00 06` constant.
- Total: 18 bytes.
- Next step: capture a second sample from a different location and diff
  bytes 11-14 to lock down the coordinate encoding.
- Fix for `enable_event("POSITION_CHANGED")`: the alias trick works
  (`POSITION_CHANGED` == `POSITION_CHANGE` in the enum), events flow
  in fine; only the body decode is missing.

**3.5.b `BSS_SETTINGS_CHANGED` (event_type=11) — ✅ decoded and wired 2026-07-04**
- Body is a bare `BSSSettings` (50 bytes) or `BSSSettingsV2` (52 bytes),
  same wire format as `ReadBSSSettingsReplyBody.bss_settings`. Not a
  group-relay message; it's the same struct the HT app receives when a
  BSS/beacon field changes.
- Field-by-field parse of the captured 52-byte payload matches the
  Tier 2.3 beacon read exactly (packet_format=APRS, aprs_callsign=
  'KC9MHE', aprs_ssid=4, aprs_symbol='/[', ptt_release_id_info='KC9MHE',
  bss_user_id=101976, location_share_interval=1800, all boolean flags
  identical). Plus one bonus: `smart_beacon_max_interval=30` (V2 tail
  `0f 00`) which isn't exposed on the high-level `BeaconSettings` yet.
- Wired: `BSSSettingsChangedEvent` in `protocol/command/notification.py`
  + `BeaconSettingsChangedEvent` in `command.py`. Now surfaces cleanly
  through the event handler API instead of falling through to
  `UnknownEvent`.
- ✅ Follow-up landed 2026-07-04: `BeaconSettings` + `BeaconSettingsArgs`
  now expose `smart_beacon_en`, `mic_e_en`, `send_id_by_aprs`,
  `smart_beacon_min_interval`, `smart_beacon_max_interval`. Round-trip
  is bit-exact.
- ✅ `REGISTER_NOTIFICATION` and `EVENT_NOTIFICATION` replies with
  `is_reply=True` now surface as `NotificationAckEvent(command, body)`
  instead of `UnknownProtocolMessage`. Controller swallows them
  silently.

**3.5.c Missing event types on N76**
During the 60s event watch, these types never fired:
- `HT_CH_CHANGED` — channel changes appear to come through
  `HT_SETTINGS_CHANGED` instead. Consider adding a controller-side
  synth event when the channel field of `Settings` mutates.
- `USER_ACTION`, `DATA_RXD`, `DATA_TXD` — not exercised (no APRS/DMR
  traffic during the test). Rerun with an APRS beacon nearby to confirm.

### 3.6 Audio TX/RX
Author flagged in the README that audio is awkward pending libsbc
bindings. Confirmed audio bytes come out of the N76 during RX with
squelch open (based on `bt-ht-n76` prior art), but decoding needs pyav
or libsbc. Out of scope for a single evening; parking here.

### 3.7 Firmware update path
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
