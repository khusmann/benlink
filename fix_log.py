#!/bin/env python3

import typing as t
import csv
import sys


def to_text(cmd: str):
    nums = [int(i, 16) for i in cmd.split(":")]
    return "".join([chr(i) if i >= 32 and i <= 126 else "." for i in nums])


reader = csv.reader(sys.stdin)

header = next(reader)
header.append("text")

rows: t.List[t.List[str]] = []

for row in reader:
    [id, dir, data] = row

    if data[:2] != "ff":
        print(
            f"Expected data in row starting with 'ff', got: {row}", file=sys.stderr
        )

    data = data[3:]

    cmds = data.split(":ff:")

    for cmd in cmds:
        cmd = "ff:" + cmd
        rows.append([id, dir, cmd, to_text(cmd)])

writer = csv.writer(sys.stdout)
writer.writerow(header)
writer.writerows(rows)
