#!/bin/env bash
REPORT_FILE=$1

cat ${REPORT_FILE%.zip}.txt | sed 's/^/# /'

unzip -p $REPORT_FILE FS/data/misc/bluetooth/logs/btsnoop_hci.log |
tshark -r - -T json |
jq -r '
    ["id", "dir", "data"],
    (.[] | [
        ._source.layers.frame."frame.number",
        if ._source.layers.frame."frame.p2p_dir" == "0" then "phone->radio" else "radio->phone" end,
        ._source.layers.btspp."btspp.data"
    ]) |
    select(.[2] != null) |
    @csv
' |
./fix_log.py