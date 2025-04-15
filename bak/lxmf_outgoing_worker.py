#!/usr/bin/env python3

import os
import time
import json
import logging
from lxmf_agent import send_audio_message

BASE_DIR = "/var/spool/asterisk/voicemail/default"
CONFIG_PATH = "/home/mkausch/dev/3620/proj/lrecomm/user_hashes.json"
POLL_INTERVAL = 5  # seconds

logging.basicConfig(
    filename="/var/log/asterisk/lxmf_worker.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# Load user:hash mapping
with open(CONFIG_PATH) as f:
    USER_HASHES = json.load(f)

def poll_and_send():
    while True:
        for mailbox, dest_hash in USER_HASHES.items():
            outgoing_path = os.path.join(BASE_DIR, mailbox, "OUTGOING")
            if not os.path.isdir(outgoing_path):
                continue

            files = sorted([f for f in os.listdir(outgoing_path) if f.endswith(".wav")])
            for fname in files:
                wav_path = os.path.join(outgoing_path, fname)
                try:
                    logging.info(f"Sending {fname} to {dest_hash}")
                    send_audio_message(wav_path, destination_hash=dest_hash, title=f"Voicemail for {mailbox}")
                    os.remove(wav_path)

                    txt_path = wav_path.replace(".wav", ".txt")
                    if os.path.exists(txt_path):
                        os.remove(txt_path)

                    logging.info(f"Sent and cleaned up {fname}")
                except Exception as e:
                    logging.error(f"Failed to send {fname}: {e}")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    poll_and_send()
