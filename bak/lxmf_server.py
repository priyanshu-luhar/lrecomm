#!/usr/bin/env python3

import pwd
import grp
import os
import shutil
import sys
import time
import json
import threading
from threading import Thread
import logging
import RNS
import LXMF
import audio_utils as audio
from LXMF import LXMessage as LXM
from audio_call import AudioCallHandler, resolve_destination  # Ensure path is correct
from datetime import datetime

# === CONFIG ===
APP_NAME = "lxmf_server"
BASE_DIR = "/var/spool/asterisk/voicemail/default"
CONFIG_PATH = "/home/mkausch/dev/3620/proj/lrecomm/user_hashes.json"
STORAGE_DIR = "/home/mkausch/.rns_lxmf_agent"
LOGFILE = os.path.join(STORAGE_DIR, "server.log")
STAMP_COST = 8
DISPLAY_NAME = "AsteriskNode"
POLL_INTERVAL = 5
VOICEMAIL_BOX = "7002"
VM_INBOX = f"/var/spool/asterisk/voicemail/default/{VOICEMAIL_BOX}/INBOX"
DISCOVERED_PATH = os.path.join(STORAGE_DIR, "discovered_peers.json")

os.makedirs(STORAGE_DIR, exist_ok=True)

# === Logging ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGFILE),
        logging.StreamHandler()
    ]
)

def rns_log_callback(message, level=RNS.LOG_INFO):
    if level >= RNS.LOG_CRITICAL:
        logging.critical(message)
    elif level >= RNS.LOG_ERROR:
        logging.error(message)
    elif level >= RNS.LOG_WARNING:
        logging.warning(message)
    elif level >= RNS.LOG_NOTICE:
        logging.info(message)
    else:
        logging.debug(message)

# === Identity ===
if os.path.exists(os.path.join(STORAGE_DIR, "identity")):
    identity = RNS.Identity.from_file(os.path.join(STORAGE_DIR, "identity"))
    logging.info("[ID] Loaded identity from disk.")
else:
    identity = RNS.Identity()
    identity.to_file(os.path.join(STORAGE_DIR, "identity"))
    logging.info("[ID] Created new identity and saved to disk.")

# === Reticulum & LXMF ===
RNS.Reticulum(loglevel=RNS.LOG_INFO, logdest=rns_log_callback)
router = LXMF.LXMRouter(storagepath=STORAGE_DIR, enforce_stamps=True)
destination = router.register_delivery_identity(identity, display_name=DISPLAY_NAME, stamp_cost=STAMP_COST)
destination.set_proof_strategy(RNS.Destination.PROVE_NONE)

# === Load user_hashes.json ===
def load_user_hashes():
    global user_hashes
    if not os.path.exists(CONFIG_PATH):
        logging.error(f"[CONFIG] Config file {CONFIG_PATH} not found.")
        user_hashes = {}
        return False
    try:
        with open(CONFIG_PATH) as f:
            user_hashes = json.load(f)
        logging.info(f"[CONFIG] Loaded config file {CONFIG_PATH}")
        return True
    except Exception as e:
        logging.error(f"[CONFIG] Failed to load: {e}")
        user_hashes = {}
        return False

load_user_hashes()

# === Delivery Handler ===
def handle_delivery(message: LXM):
    try:
        if not isinstance(message, LXM):
            logging.warning("[DELIVERY] Non-LXMF message. Ignoring.")
            return

        if not user_hashes:
            logging.warning("[INCOMING] No user_hashes.json loaded.")
            return

        source_hash = message.source_hash.hex().lower()
        matched_mailbox = next((mb for mb, h in user_hashes.items() if h.lower() == source_hash), None)
        if not matched_mailbox:
            logging.warning(f"[INCOMING] No match for source hash {source_hash}")
            return

        if 7 not in message.fields:
            logging.warning("[INCOMING] No audio field present.")
            return

        inbox_path = os.path.join(BASE_DIR, matched_mailbox, "INBOX")
        os.makedirs(inbox_path, exist_ok=True)
        existing = [f for f in os.listdir(inbox_path) if f.startswith("msg") and f.endswith(".wav")]
        nums = [int(f[3:7]) for f in existing if f[3:7].isdigit()]
        next_idx = max(nums) + 1 if nums else 0
        base_filename = f"msg{next_idx:04d}"
        new_wav_path = os.path.join(inbox_path, f"{base_filename}.wav")
        new_txt_path = os.path.join(inbox_path, f"{base_filename}.txt")

        decoded_wav, duration = audio.save_and_decode_audio(
            message.fields, output_path=new_wav_path
        )
        if not decoded_wav or not os.path.isfile(decoded_wav):
            logging.warning("[AUDIO] Failed to decode message.")
            return

        create_asterisk_metadata_txt(new_txt_path, matched_mailbox, message, duration)
        os.chmod(new_txt_path, 0o660)
        logging.info(f"[DELIVERY] Saved to {new_wav_path} for mailbox {matched_mailbox}")

    except Exception as e:
        logging.error(f"[DELIVERY] Error: {e}")

def create_asterisk_metadata_txt(path, mailbox, message, duration):
    now = int(time.time())
    human_time = time.strftime("%a %b %d %I:%M:%S %p UTC %Y", time.gmtime(now))
    serial = "00000001"
    msg_id = f"{now}-{serial}"
    txt = f""";
; Message Information file
;
[message]
origmailbox={mailbox}
context=default
macrocontext=
exten={mailbox}
rdnis=unknown
priority=2
callerchan=PJSIP/{mailbox}-{RNS.prettyhexrep(message.source_hash)}
callerid={mailbox}
origdate={human_time}
origtime={now}
category=
msg_id={msg_id}
flag=
duration={duration}
"""
    with open(path, "w") as f:
        f.write(txt)

# === Outgoing Poller ===
outgoing_status = {"pending": 0, "sent": 0, "errors": 0}

def poll_outgoing():
    while True:
        try:
            if not user_hashes:
                logging.warning("[POLL] No user_hashes loaded.")
                continue

            total_pending = 0
            for mailbox, dest_hash in user_hashes.items():
                outbox = os.path.join(BASE_DIR, mailbox, "OUTGOING")
                sentbox = os.path.join(BASE_DIR, mailbox, "SENT")
                os.makedirs(outbox, exist_ok=True)
                os.makedirs(sentbox, exist_ok=True)

                wavs = sorted(f for f in os.listdir(outbox) if f.endswith(".wav"))
                total_pending += len(wavs)

                for fname in wavs:
                    wav_path = os.path.join(outbox, fname)
                    try:
                        msg = audio.create_lxmf_audio_message(
                            destination=resolve_destination(dest_hash),
                            source=destination,
                            input_wav=wav_path,
                            title=f"Voicemail for {mailbox}",
                            codec="codec2"
                        )
                        if msg:
                            router.handle_outbound(msg)
                            shutil.move(wav_path, os.path.join(sentbox, fname))

                            txt_path = wav_path.replace(".wav", ".txt")
                            if os.path.exists(txt_path):
                                shutil.move(txt_path, os.path.join(sentbox, os.path.basename(txt_path)))
                            outgoing_status["sent"] += 1
                        else:
                            raise Exception("Message build failed.")

                    except Exception as e:
                        outgoing_status["errors"] += 1
                        logging.error(f"[SEND] Failed: {e}")

            outgoing_status["pending"] = total_pending
        except Exception as e:
            logging.error(f"[POLL] Poll error: {e}")
        time.sleep(POLL_INTERVAL)


# === Menu System ===
def menu_loop(call_handler=None):
    try:
        while True:
            print("\n=== LXMF SERVER MENU ===")
            print(f"[+] Listening on: {RNS.prettyhexrep(destination.hash)}")
            print(f"[+] Pending messages : {outgoing_status['pending']}")
            print(f"[+] Sent successfully : {outgoing_status['sent']}")
            print(f"[+] Errors encountered: {outgoing_status['errors']}")
            print("Options:")
            print("  r) Reload user_hashes.json")
            print("  a) Announce LXMF presence")
            print("  c) Call a peer via Codec2")
            print("  d) Dial a peer")
            print("  q) Quit")

            choice = input("Select: ").strip().lower()

            if choice == "q":
                print("Shutting down...")
                os._exit(0)
            elif choice == "r":
                if load_user_hashes():
                    print("Reloaded successfully.")
            elif choice == "a":
                router.announce(destination.hash)
                print("Announce sent.")
            elif choice == "c":
                target_hash = input("Enter peer destination hash: ").strip()
                call_handler.dial(target_hash)
            elif choice == "d" and call_handler:
                dest = input("Enter destination hash: ").strip()
                call_handler.dial(dest)
    except KeyboardInterrupt:
        print("Interrupted.")
        os._exit(0)

# 98fcfffa274a97a11227fb7e7f4a6966
# === Main ===
if __name__ == "__main__":
    logging.info("[BOOT] LXMF Server starting...")
    router.register_delivery_callback(handle_delivery)

    threading.Thread(target=poll_outgoing, daemon=True).start()
    logging.info("[POLL] Outgoing poller started.")

    call_handler = AudioCallHandler(identity=identity, mailbox=VOICEMAIL_BOX, inbox_path=VM_INBOX)
    call_handler.start_listening()
    logging.info("[VOICE] AudioCallHandler is listening...")

    menu_loop(call_handler=call_handler)
