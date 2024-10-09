#!/bin/env python3

import csv
import sys


def to_text(cmd: bytes):
    return "".join([chr(i) if i >= 32 and i <= 126 else "." for i in cmd])


reader = csv.DictReader(sys.stdin)

header = reader.fieldnames

if (header is None):
    print("No header found in input", file=sys.stderr)
    sys.exit(1)

new_header = [*header, "msg_type", "cmd", "text"]

writer = csv.DictWriter(sys.stdout, fieldnames=new_header)
writer.writeheader()

for msg in reader:
    data = bytes.fromhex(msg["data"].replace(":", ""))

    if not data[:3] == b"\xff\x01\x00":
        print(
            f"Expected data[:3] = 'ff:01:00', got: {msg}", file=sys.stderr
        )
        continue

    msg_len = data[3]

    if not data[4:6] == b"\x00\x02":
        print(
            f"Expected data[4:6] = '00:02', got: {msg}", file=sys.stderr
        )
        continue

    match data[6]:
        case 0x00:
            msg_type = "post"
        case 0x80:
            msg_type = "reply"
        case _:
            print(
                f"Expected data[6] = '00' or '80', got: {msg}", file=sys.stderr
            )
            continue

    match data[7]:
        case 0x09:
            cmd = "aprs (0x09)"
        case _:
            cmd = "unknown (0x{:02x})".format(data[7])

    text = data[8:]

    if len(text) != msg_len:
        print(
            f"Expected msg_len = {msg_len}, got: {len(text)}", file=sys.stderr
        )
        print(f"msg: {text}", file=sys.stderr)
        continue

    writer.writerow({
        **msg,
        "msg_type": msg_type,
        "cmd": cmd,
        "text": to_text(text)
    })
