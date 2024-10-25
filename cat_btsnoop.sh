#!/bin/env bash

REPORT_FILE="$1"

decode_btsnoop() {
    local filename="$1"

    # Check if the file exists in the zip archive
    if unzip -l "$REPORT_FILE" | awk '{print $NF}' | grep -q "^$filename$"; then
        # Print the file's contents to stdout
        unzip -p "$REPORT_FILE" "$filename" | tshark -r - -T json |
        jq -r '
            (.[] | [
                ._source.layers.frame."frame.number",
                if ._source.layers.frame."frame.p2p_dir" == "0" then "phone->radio" else "radio->phone" end,
                ._source.layers.btspp."btspp.data"
            ]) |
            select(.[2] != null) |
            @csv
        ' 
    fi
}

echo 'id,dir,data'

decode_btsnoop "FS/data/misc/bluetooth/logs/btsnoop_hci.log.last"
decode_btsnoop "FS/data/misc/bluetooth/logs/btsnoop_hci.log"