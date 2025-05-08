#!/bin/bash

LOGFILE="/var/log/asterisk/extern_notify_test.log"
echo "[$(date)] extern_notify triggered with args: $@" >> $LOGFILE

# Lightweight enqueue step, pure Python, no Conda needed
/usr/bin/python3 /home/mkausch/dev/3620/proj/lrecomm/enqueue_voicemail.py "$@" >> $LOGFILE 2>&1