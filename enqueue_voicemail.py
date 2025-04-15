#!/usr/bin/env python3

import os
import sys
import shutil
from datetime import datetime

VOICEMAIL_BASE = "/var/spool/asterisk/voicemail"

def get_next_available_index(folder):
    existing = [f for f in os.listdir(folder) if f.startswith("msg") and f.endswith(".wav")]
    nums = [int(f[3:7]) for f in existing if f[3:7].isdigit()]
    return max(nums) + 1 if nums else 0

def enqueue(context, mailbox):
    inbox = os.path.join(VOICEMAIL_BASE, context, mailbox, "INBOX")
    outbox = os.path.join(VOICEMAIL_BASE, context, mailbox, "OUTGOING")

    os.makedirs(outbox, exist_ok=True)

    # Find the most recently created msg*.wav file
    wavs = [f for f in os.listdir(inbox) if f.startswith("msg") and f.endswith(".wav")]
    if not wavs:
        print(f"[{datetime.now()}] No voicemails found in {inbox}")
        return

    latest_wav = max(wavs, key=lambda f: os.path.getctime(os.path.join(inbox, f)))
    txt_file = latest_wav.replace(".wav", ".txt")

    # Generate a new msgXXXX name in OUTGOING
    next_idx = get_next_available_index(outbox)
    new_wav = f"msg{next_idx:04d}.wav"
    new_txt = f"msg{next_idx:04d}.txt"

    # Move to OUTGOING
    shutil.move(os.path.join(inbox, latest_wav), os.path.join(outbox, new_wav))
    txt_path = os.path.join(inbox, txt_file)
    if os.path.exists(txt_path):
        shutil.move(txt_path, os.path.join(outbox, new_txt))

    print(f"[{datetime.now()}] Moved {latest_wav} → {new_wav}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: enqueue_voicemail.py <context> <mailbox>")
        sys.exit(1)
    enqueue(sys.argv[1], sys.argv[2])
