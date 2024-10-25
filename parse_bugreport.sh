#!/bin/env bash
REPORT_FILE=$1

cat ${REPORT_FILE%.zip}.txt | sed 's/^/# /'
echo
./cat_btsnoop.sh $REPORT_FILE | ./fix_log.py