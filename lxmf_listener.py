# if on windows and using wsl, uses these commands in powershell:
# usbipd list (to get the port number)
# usbipd bind --busid 3-2  (match 3-2 to the port number from usbipd list)

# and then 

# usbipd attach --wsl --busid 3-2 
# then it should be listed in the devices
# can view it with ls /dev/tty* 
# may be something like /dev/ttyACM0


import os
import time
import logging
import RNS
import LXMF
import audio_utils as audio
from LXMF import LXMessage as LXM

# === CONFIG ===
APP_NAME = "lxmf_listener"
STORAGE_DIR = os.path.expanduser(f"~/.rns_{APP_NAME}")
IDENTITY_FILE = os.path.join(STORAGE_DIR, "identity")
LOGFILE = os.path.join(STORAGE_DIR, "listener.log")
DISPLAY_NAME = "AudioNode"
STAMP_COST = 8
ANNOUNCE_INTERVAL = 30  # seconds
TEST_WAV_PATH = "/home/mkausch/dev/3620/proj/bee.wav"
CAGE = "656558850a2b2cd46892a2530b3affc4"
ARM_6 = "8bfdd2075c73a7d1c640e51df4c979ef"


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

# === Identity ===
if os.path.exists(IDENTITY_FILE):
    identity = RNS.Identity.from_file(IDENTITY_FILE)
    logging.info("[ID] Loaded identity from disk.")
else:
    identity = RNS.Identity()
    identity.to_file(IDENTITY_FILE)
    logging.info("[ID] Created new identity and saved to disk.")

# === Reticulum & LXMF ===
RNS.Reticulum()  # will use system config or ~/.reticulum
router = LXMF.LXMRouter(storagepath=STORAGE_DIR, enforce_stamps=True)
for iface in RNS.Transport.interfaces:
    logging.info(f"[IFACE] Found interface: {iface.name}, via port: {getattr(iface, 'serial_port', 'n/a')}")


# Register destination for receiving
destination = router.register_delivery_identity(
    identity,
    display_name=DISPLAY_NAME,
    stamp_cost=STAMP_COST
)

# === Handle incoming messages ===
def handle_delivery(message: LXM):
    try:
        time_string = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(message.timestamp))
        signature_string = "Validated" if message.signature_validated else "Invalid or Unknown"
        stamp_string = "Validated" if message.stamp_valid else "Invalid"


        logging.info("\t+--- LXMF RECEIVED FROM PIPE ---------------------------")
        logging.info(f"\t| Source hash          : {RNS.prettyhexrep(message.source_hash)}")
        logging.info(f"\t| Source instance      : {message.get_source()}")
        logging.info(f"\t| Destination hash     : {RNS.prettyhexrep(message.destination_hash)}")
        logging.info(f"\t| Destination instance : {message.get_destination()}")
        logging.info(f"\t| Encryption           : {message.transport_encryption}")
        logging.info(f"\t| Timestamp            : {time_string}")
        logging.info(f"\t| Title                : {message.title_as_string()}")
        logging.info(f"\t| Content              : {message.content_as_string()}")
        logging.info(f"\t| Fields               : {message.fields}")
        if message.ratchet_id:
            logging.info(f"\t| Ratchet              : {RNS.Identity._get_ratchet_id(message.ratchet_id)}")
        logging.info(f"\t| Signature            : {signature_string}")
        logging.info(f"\t| Stamp                : {stamp_string}")
        logging.info("\t+-------------------------------------------------------")


        # Detect and handle incoming audio message
        if message.fields and 7 in message.fields:
            logging.info("[AUDIO] Audio field detected. Attempting to decode...")
            decoded_path = audio.save_and_decode_audio(message.fields)

            if decoded_path:
                logging.info(f"[AUDIO] Audio saved and decoded to: {decoded_path}")
                print(f"[🎧 AUDIO] Message from {RNS.prettyhexrep(message.source_hash)} saved to {decoded_path}")
            else:
                logging.warning("[AUDIO] Failed to decode audio message.")
        
        reply = audio.create_lxmf_audio_message(message.source, destination, TEST_WAV_PATH, codec="codec2", title="Voice Message", bitrate=1200)
            
        router.handle_outbound(reply)
        print("[AudioNode] Replied.")


    except Exception as e:
        logging.error(f"Error handling message: {e}")

router.register_delivery_callback(handle_delivery)

logging.info(f"[READY] Listening on: {RNS.prettyhexrep(destination.hash)}")

# === Announce destination periodically ===

def periodic_announce():
    boot_time = time.time()
    while True:
        success = router.announce(destination.hash)
        logging.info("[AudioNode] Announced to LXMF network. Success: {}".format(success))
        # if time.time() - boot_time < 10:

        pri_bytes = bytes.fromhex(ARM_6)

        if not RNS.Transport.has_path(pri_bytes):
            RNS.log("Destination is not yet known. Requesting path and waiting for announce to arrive...")
            RNS.Transport.request_path(pri_bytes)
            while not RNS.Transport.has_path(pri_bytes):
                time.sleep(0.1)

        # Recall the server identity
        recipient_identity = RNS.Identity.recall(pri_bytes)

        pri_dest = RNS.Destination(recipient_identity, RNS.Destination.OUT, RNS.Destination.SINGLE, "lxmf", "delivery")

        reply = audio.create_lxmf_audio_message(pri_dest, destination, TEST_WAV_PATH, codec="codec2", title="Voice Message", bitrate=1200)
        router.handle_outbound(reply)
        print("[AudioNode] Sent CAGE a message.")
        time.sleep(5)  # fast announce for first 10 seconds
        # else:
            # time.sleep(120)  # slow down after  



# Start it explicitly with error logging
try:
    import threading
    announce_thread = threading.Thread(target=periodic_announce, daemon=True)
    announce_thread.start()
    logging.info("[ANNOUNCE] Announce thread started.")
except Exception as e:
    logging.error(f"[ANNOUNCE] Failed to start announce thread: {e}")

# === Keep the script alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    logging.info("Exiting.")
