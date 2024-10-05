#!/bin/env bash
unzip -p $1 FS/data/misc/bluetooth/logs/btsnoop_hci.log |
tshark -r - -T json |
jq -r '
    ["id", "dir", "channel", "data"],
    (.[] | [
        ._source.layers.frame."frame.number",
        if ._source.layers.frame."frame.p2p_dir" == "0" then "phone->radio" else "radio->phone" end,
        ._source.layers.btrfcomm."btrfcomm.address"."btrfcomm.dlci_tree"."btrfcomm.channel",
        ._source.layers.data."data.data" // ._source.layers.btspp."btspp.data"
    ]) |
    select(.[3] != null) |
    @csv
'