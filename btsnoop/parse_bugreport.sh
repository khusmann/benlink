#!/bin/env bash
REPORT_FILE_ZIP=$1

report_file="${REPORT_FILE_ZIP%.zip}.txt"

if [ -f "$report_file" ]; then
    cat "$report_file" | sed 's/^/# /'
fi
echo
./cat_btsnoop.sh $REPORT_FILE_ZIP | ./fix_log.py