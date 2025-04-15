
import os
import time
import logging
import RNS
import LXMF
import audio_utils as audio
from LXMF import LXMessage as LXM

APP_NAME = "lxmf_agent"
STORAGE_DIR = STORAGE_DIR = "/home/mkausch/.rns_lxmf_agent"
IDENTITY_FILE = os.path.join(STORAGE_DIR, "identity")
DEFAULT_DESTINATION_HASH = "8bfdd2075c73a7d1c640e51df4c979ef"  # hardcoded fallback
DISPLAY_NAME = "AudioNode"
STAMP_COST = 8

# Setup
os.makedirs(STORAGE_DIR, exist_ok=True)

# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s [%(levelname)s] %(message)s",
#     handlers=[
#         logging.FileHandler(os.path.join(STORAGE_DIR, "agent.log")),
#         logging.StreamHandler()
#     ]
# )

_initialized = False
_router = None
_identity = None
_local_source = None

def initialize_lxmf():
    global _initialized, _router, _identity, _local_source
    if _initialized:
        return

    if os.path.exists(IDENTITY_FILE):
        _identity = RNS.Identity.from_file(IDENTITY_FILE)
        logging.info("[ID] Loaded identity from disk.")
    else:
        _identity = RNS.Identity()
        _identity.to_file(IDENTITY_FILE)
        logging.info("[ID] Created new identity and saved to disk.")

    RNS.Reticulum()
    _router = LXMF.LXMRouter(storagepath=STORAGE_DIR, enforce_stamps=True)
    _local_source = _router.register_delivery_identity(
        _identity,
        display_name=DISPLAY_NAME,
        stamp_cost=STAMP_COST
    )
    logging.info(f"[READY] Local destination: {RNS.prettyhexrep(_local_source.hash)}")
    _initialized = True

def resolve_destination(hex_hash):
    pri_bytes = bytes.fromhex(hex_hash)
    if not RNS.Transport.has_path(pri_bytes):
        RNS.log("Requesting path to destination...")
        RNS.Transport.request_path(pri_bytes)
        while not RNS.Transport.has_path(pri_bytes):
            time.sleep(0.1)

    recipient_identity = RNS.Identity.recall(pri_bytes)
    return RNS.Destination(recipient_identity, RNS.Destination.OUT, RNS.Destination.SINGLE, "lxmf", "delivery")

def send_audio_message(audio_path, destination_hash=None, title="Voice Message", bitrate=1200):
    initialize_lxmf()

    dest_hash = destination_hash or DEFAULT_DESTINATION_HASH
    destination = resolve_destination(dest_hash)

    message = audio.create_lxmf_audio_message(
        destination,
        _local_source,
        audio_path,
        codec="codec2",
        title=title,
        bitrate=bitrate
    )
    _router.handle_outbound(message)
    logging.info("[LXMF] Audio message sent.")
