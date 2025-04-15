#!/usr/bin/env python3

import os
import sys
import json
import logging
import argparse
import shutil
import time
from datetime import datetime
from lxmf_agent import send_audio_message

# --- Configuration ---
MAILBOX_BASE = "/var/spool/asterisk/voicemail"
LOG_PATH = "/home/mkausch/dev/3620/proj/lrecomm/logs/externnotify.log"
CONFIG_PATH = "/home/mkausch/dev/3620/proj/lrecomm/user_hashes.json"  # <-- Path to user:hash config

# --- Setup Logging ---
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# --- Argument Parser ---
parser = argparse.ArgumentParser(description="Triggered by externnotify to forward new voicemail.")
parser.add_argument("context", help="Voicemail context (e.g., default)")
parser.add_argument("mailbox", help="Mailbox number (e.g., 6001)")
parser.add_argument("inbox_count", type=int, help="Count of new messages in INBOX")
parser.add_argument("old_count", type=int, help="Count of messages in Old")
parser.add_argument("urgent_count", type=int, help="Count of messages in Urgent")

args = parser.parse_args()

# --- Paths ---
inbox_path = os.path.join(MAILBOX_BASE, args.context, args.mailbox, "INBOX")
old_path = os.path.join(MAILBOX_BASE, args.context, args.mailbox, "Old")

# --- Load Routing Config ---
try:
    with open(CONFIG_PATH, "r") as f:
        USER_HASHES = json.load(f)
except Exception as e:
    logging.error(f"Failed to load config file {CONFIG_PATH}: {e}")
    USER_HASHES = {}

def get_latest_msg():
    """Return the lowest-numbered msgXXXX.wav file in INBOX."""
    try:
        wavs = [f for f in os.listdir(inbox_path) if f.startswith("msg") and f.endswith(".wav")]
        if not wavs:
            return None
        wavs.sort(key=lambda f: int(f[3:7]))
        return wavs[0]
    except Exception as e:
        logging.error(f"Error accessing INBOX: {e}")
        return None

def get_next_available_msg_number(folder):
    existing = [f for f in os.listdir(folder) if f.startswith("msg") and f.endswith(".wav")]
    numbers = [int(f[3:7]) for f in existing]
    return max(numbers) + 1 if numbers else 0

def forward_and_archive(wav_file):
    wav_path = os.path.join(inbox_path, wav_file)
    txt_file = wav_file.replace(".wav", ".txt")
    txt_path = os.path.join(inbox_path, txt_file)

    dest_hash = USER_HASHES.get(args.mailbox)
    if not dest_hash:
        logging.warning(f"No LXMF destination configured for mailbox {args.mailbox}")
        return

    try:
        # Send audio to LXMF destination
        send_audio_message(wav_path, destination_hash=dest_hash, title=f"Voicemail from {args.mailbox}")

        # Move WAV and TXT to Old with new name
        new_index = get_next_available_msg_number(old_path)
        new_wav_name = f"msg{new_index:04d}.wav"
        new_txt_name = f"msg{new_index:04d}.txt"

        shutil.move(wav_path, os.path.join(old_path, new_wav_name))
        if os.path.exists(txt_path):
            shutil.move(txt_path, os.path.join(old_path, new_txt_name))

        logging.info(f"Forwarded and archived message: {new_wav_name}")
    except Exception as e:
        logging.error(f"Failed to process message {wav_file}: {e}")

def main():
    logging.info(f"Extern notify triggered for: context={args.context}, mailbox={args.mailbox}, inbox={args.inbox_count}")
    while True:
        latest = get_latest_msg()
        if not latest:
            break
        forward_and_archive(latest)
    logging.info("No more messages to process.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.exception(f"Unhandled exception: {e}")
        sys.exit(1)
