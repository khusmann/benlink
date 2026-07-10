#!/usr/bin/env python3
"""Tier 4 — RFCOMM audio channel resolver smoke.

Just resolves the BS AOC (Benshi audio) channel via SDP; does not open the
audio socket (which would need the radio in a specific state).
"""
import benlink.link as link
from _teelog import setup_teelog

setup_teelog(__file__)

ADDR = "38:D2:00:01:74:D9"
print(f"[t4-audio] resolving Benshi audio channel on {ADDR}...")
try:
    ch = link._resolve_rfcomm_channel(ADDR, link.BENSHI_AUDIO_SERVICE_UUID)
    print(f"[t4-audio] audio RFCOMM channel: {ch}")
except NotImplementedError as e:
    print(f"[t4-audio] resolver said: {e}")
