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
from LXST.Primitives.Telephony import Telephone
from LXST.Sinks import LineSink
import wave
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
TEST_WAV_PATH = "/home/mkausch/dev/3620/proj/bee.wav"

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
# RNS.Reticulum(logdest="rns.log", loglevel=None, logdest=None,loglevel=RNS.LOG_WARNING)
router = LXMF.LXMRouter(storagepath=STORAGE_DIR, enforce_stamps=True)
destination = router.register_delivery_identity(identity, display_name=DISPLAY_NAME, stamp_cost=STAMP_COST)
destination.set_proof_strategy(RNS.Destination.PROVE_NONE)
RNS.log
# Optional: silence internal error/warning logs too
# RNS.log_to_console = False



def fix_voicemail_permissions(filepath):
    try:
        # uid = pwd.getpwnam("asterisk").pw_uid
        # gid = grp.getgrnam("asterisk").gr_gid
        # os.chown(filepath, uid, gid)
        os.chmod(filepath, 0o660)  # rw-rw----
        logging.debug(f"[PERMS] Set ownership and permissions for {filepath}")
    except Exception as e:
        logging.warning(f"[PERMS] Failed to set permissions for {filepath}: {e}")


# Load user_hashes.json dynamically
def load_user_hashes():
    """Load user_hashes.json file."""
    global user_hashes
    if not os.path.exists(CONFIG_PATH):
        logging.error(f"[CONFIG] Config file {CONFIG_PATH} not found.")
        user_hashes = {}
        return False
    else:
        try:
            with open(CONFIG_PATH) as f:
                user_hashes = json.load(f)
            logging.info(f"[CONFIG] Loaded config file {CONFIG_PATH}")
            return True
        except json.JSONDecodeError as e:
            logging.error(f"[CONFIG] Failed to parse config file {CONFIG_PATH}: {e}")
            user_hashes = {}
            return False
        except Exception as e:
            logging.error(f"[CONFIG] Error loading config file {CONFIG_PATH}: {e}")
            user_hashes = {}
            return False
load_user_hashes()

# === Creates Metadata File For Voicemail File ===
def create_asterisk_metadata_txt(path, mailbox, message, duration):
    """Creates a valid Asterisk .txt metadata file next to the WAV file."""
    now = int(time.time())
    human_time = time.strftime("%a %b %d %I:%M:%S %p UTC %Y", time.gmtime(now))
    serial = "00000001"  # You could increment this if needed
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
    logging.info(f"[METADATA] Created metadata file {path}")

DISCOVERED_PATH = os.path.join(STORAGE_DIR, "discovered_peers.json")

# class BuddyAnnounceHandler:
#     def __init__(self, aspect_filter="lxmf.delivery"):
#         self.aspect_filter = aspect_filter

#     def received_announce(self, destination_hash, announced_identity, app_data):
#         hex_hash = destination_hash.hex().lower()

#         if hex_hash in user_hashes.values():
#             return  # Already known user, skip

#         name = announced_identity.display_name if announced_identity else "Unknown"

#         # Load discovered_peers.json
#         if os.path.exists(DISCOVERED_PATH):
#             with open(DISCOVERED_PATH, "r") as f:
#                 discovered = json.load(f)
#         else:
#             discovered = {}

#         if hex_hash not in discovered:
#             logging.info(f"[DISCOVERY] New LXMF peer: {name} ({hex_hash})")

#         discovered[hex_hash] = {
#             "name": name,
#             "pubkey": RNS.hexrep(announced_identity.hash),
#             "last_seen": int(time.time())
#         }

#         with open(DISCOVERED_PATH, "w") as f:
#             json.dump(discovered, f, indent=2)

class LXMFAnnounceHandler:
    def __init__(self, aspect_filter=None):
        self.aspect_filter = aspect_filter

    def received_announce(self, destination_hash, announced_identity, app_data):
        hexhash = RNS.prettyhexrep(destination_hash)
        logging.info(f"[ANNOUNCE] Received announce from: <{hexhash}>")

        if app_data:
            try:
                decoded = app_data.decode("utf-8")
                logging.info(f"[ANNOUNCE] App data in announce: {decoded}")
            except UnicodeDecodeError:
                hex_data = app_data.hex()
                logging.debug(f"[ANNOUNCE] App data (raw hex): {hex_data}")


VOICEMAIL_BOX = "7002"
VM_INBOX = f"/var/spool/asterisk/voicemail/default/{VOICEMAIL_BOX}/INBOX"

def create_asterisk_metadata_txt(txt_path, duration=5):
    timestamp = int(time.time())
    dt = datetime.now()
    with open(txt_path, "w") as f:
        f.write(f"""{timestamp}|{dt.hour}:{dt.minute}|{dt.strftime('%A')}|{dt.strftime('%B')} {dt.day} {dt.year}||callerid=""|duration={duration}\n""")

def handle_incoming_voice_calls(identity):
    telephone = Telephone(identity)
    logging.info("[Voice] Voice listener thread started")

    while True:
        try:
            if telephone.is_ringing:
                logging.info("[Voice] Incoming call detected. Answering...")
                base_name = f"msg{int(time.time()) % 10000:04d}"
                wav_path = os.path.join(VM_INBOX, f"{base_name}.wav")
                txt_path = os.path.join(VM_INBOX, f"{base_name}.txt")

                telephone.set_speaker(LineSink(wav_path))
                telephone.answer()

                # Wait until call ends
                while telephone.is_in_call:
                    time.sleep(1)

                logging.info(f"[Voice] Call ended. Saved to {wav_path}")
                create_asterisk_metadata_txt(txt_path)
                os.chmod(wav_path, 0o660)
                os.chmod(txt_path, 0o660)

        except Exception as e:
            logging.error(f"[Voice] Error in call handling: {e}")
        time.sleep(1)


# === Handle incoming messages ===
def handle_delivery(message: LXM):
    try:
        time_string = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(message.timestamp))
        logging.info(f"[INCOMING] From {RNS.prettyhexrep(message.source_hash)} at {time_string}")

        if not isinstance(message, LXM):
            logging.warning("[DELIVERY] Received non-LXMF message. Ignoring.")
            return

        if not user_hashes:
            logging.warning("[INCOMING] No user_hashes.json found.")
            return
        

        source_hash = message.source_hash.hex().lower()
        matched_mailbox = None

        for mailbox, hashval in user_hashes.items():
            logging.info(f"[DEBUG] raw source_hash: {message.source_hash}")
            logging.info(f"[DEBUG] .hex() version: {message.source_hash.hex()}")

            logging.info(f"[INCOMING] Checking {hashval.lower()} against {source_hash}")
            if hashval.lower() == source_hash:
                matched_mailbox = mailbox
                break

        if not matched_mailbox:
            logging.warning(f"[INCOMING] No matching mailbox for source hash {source_hash}")
            return

        if 7 not in message.fields:
            logging.warning("[INCOMING] No audio field present in message.")
            return

        # Determine next msgXXXX.wav name early
        inbox_path = os.path.join(BASE_DIR, matched_mailbox, "INBOX")
        os.makedirs(inbox_path, exist_ok=True)
        existing = [f for f in os.listdir(inbox_path) if f.startswith("msg") and f.endswith(".wav")]
        nums = [int(f[3:7]) for f in existing if f[3:7].isdigit()]
        next_idx = max(nums) + 1 if nums else 0
        base_filename = f"msg{next_idx:04d}"
        new_wav_path = os.path.join(inbox_path, f"{base_filename}.wav")
        new_txt_path = os.path.join(inbox_path, f"{base_filename}.txt")

        # Decode audio directly into final path
        decoded_wav, duration = audio.save_and_decode_audio(
            message.fields,
            output_dir=None,
            output_path=new_wav_path
        )
        if not decoded_wav or not os.path.isfile(decoded_wav):
            logging.warning("[AUDIO] Failed to decode incoming message.")
            return

        # Create metadata file
        create_asterisk_metadata_txt(new_txt_path, matched_mailbox, message, duration)
        os.chmod(new_txt_path, 0o660)
        logging.info(f"[DELIVERY] Saved message to {new_wav_path} for mailbox {matched_mailbox}")

    except Exception as e:
        logging.error(f"[DELIVERY] Error handling message: {e}")


# RNS.Transport.register_announce_handler(LXMFAnnounceHandler())
# logging.info("[ANNOUNCE] LXMF announce handler registered.")
# router.register_delivery_callback(handle_delivery)
# logging.debug("[DELIVERY] Delivery handler registered.")

# === Outgoing poller ===
outgoing_status = {"pending": 0, "sent": 0, "errors": 0}

def poll_outgoing():
    while True:
        try:
            if not user_hashes:
                logging.warning("[POLL] No user_hashes loaded; skipping poll.")
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
                        logging.info(f"[SEND] {fname} to {dest_hash}")
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
                            raise Exception("Failed to build LXMF message")

                    except Exception as e:
                        outgoing_status["errors"] += 1
                        logging.error(f"[SEND] Failed to send {fname}: {e}")

            outgoing_status["pending"] = total_pending
        except Exception as e:
            logging.error(f"[POLL] Error in poller: {e}")
        time.sleep(POLL_INTERVAL)

def resolve_destination(hex_hash):
    pri_bytes = bytes.fromhex(hex_hash)
    if not RNS.Transport.has_path(pri_bytes):
        RNS.Transport.request_path(pri_bytes)
        while not RNS.Transport.has_path(pri_bytes):
            time.sleep(0.2)
    recipient = RNS.Identity.recall(pri_bytes)
    return RNS.Destination(recipient, RNS.Destination.OUT, RNS.Destination.SINGLE, "lxmf", "delivery")

# === Menu Thread ===
def menu_loop():
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
            print("  q) Quit")
            print("  b) View discovered peers")
            print("  s) Select a discovered peer to forward to (sets as 6001)")


            choice = input("Select: ").strip().lower()

            if choice == "q":
                print("Shutting down...")
                os._exit(0)
            elif choice == "r":
                print("Reloading user_hashes.json...")
                if load_user_hashes():
                    print("Reloaded successfully.")
                else:
                    print("Failed to reload user_hashes.json.")
            elif choice == "a":
                print("Announcing to LXMF network...")
                success = router.announce(destination.hash)
                logging.info(f"[ANNOUNCE] Manual announce: Success = {success}")
                print("Announce sent.\n")
            elif choice == "b":
                if not os.path.exists(DISCOVERED_PATH):
                    print("No peers discovered yet.")
                    continue

                with open(DISCOVERED_PATH, "r") as f:
                    peers = json.load(f)

                print("\n--- Discovered LXMF Peers ---")
                for hashval, data in peers.items():
                    name = data.get("name", "Unknown")
                    seen = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(data.get("last_seen", 0)))
                    print(f"{name:<20}  {hashval}  (last seen: {seen})")
            elif choice == "s":
                if not os.path.exists(DISCOVERED_PATH):
                    print("No discovered peers available.")
                    continue

                with open(DISCOVERED_PATH, "r") as f:
                    peers = json.load(f)

                if not peers:
                    print("No discovered peers found.")
                    continue

                print("\n--- Select Peer to Assign as 6001 ---")
                sorted_peers = list(peers.items())
                for i, (hashval, data) in enumerate(sorted_peers):
                    name = data.get("name", "Unknown")
                    print(f"{i}) {name:<20}  {hashval}")

                idx = input("Enter the number of the peer to assign to 6001: ").strip()
                if not idx.isdigit() or int(idx) < 0 or int(idx) >= len(sorted_peers):
                    print("Invalid selection.")
                    continue

                selected_hash = sorted_peers[int(idx)][0]

                # Load and update user_hashes.json
                try:
                    if os.path.exists(CONFIG_PATH):
                        with open(CONFIG_PATH, "r") as f:
                            current_hashes = json.load(f)
                    else:
                        current_hashes = {}

                    current_hashes["6001"] = selected_hash

                    with open(CONFIG_PATH, "w") as f:
                        json.dump(current_hashes, f, indent=2)

                    print(f"Assigned {selected_hash} to SIP mailbox 6001.")
                    logging.info(f"[CONFIG] Updated 6001 -> {selected_hash} in user_hashes.json")

                    load_user_hashes()

                except Exception as e:
                    print(f"Failed to update config: {e}")
                    logging.error(f"[CONFIG] Failed to assign peer: {e}")



    except KeyboardInterrupt:
        print("Exiting.")
        os._exit(0)


# === Start threads ===
if __name__ == "__main__":
    logging.info("[BOOT] LXMF Server starting...")
    threading.Thread(target=poll_outgoing, daemon=True).start()
    # threading.Thread(target=handle_incoming_voice_calls, args=(identity,), daemon=True).start()
    logging.info("[POLL] Outgoing poller started.")
    menu_loop()
