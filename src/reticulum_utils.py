import os
import RNS
import sys
import LXMF
from LXMF import LXMessage as LXM
from database_utils import *
from globals import *


def make_identity():
    my_id = RNS.Identity()
    my_id.to_file(IDENTITY_PATH)

def load_identity():
    my_id = RNS.Identity.from_file(IDENTITY_PATH)
    return my_id

def rns_setup(configpath=None):
    #global reticulum, my_destination, router
    reticulum = RNS.Reticulum(configpath)
    
    router = LXMF.LXMRouter(storagepath=STORAGE_DIR, enforce_stamps=True)
    
    if not os.path.exists(IDENTITY_PATH):
        make_identity()
        
    identity = load_identity()
    my_destination = router.register_delivery_identity(identity, display_name=DISPLAY_NAME, stamp_cost=STAMP_COST)

    broadcast_destination = RNS.Destination(
        None,
        RNS.Destination.IN,
        RNS.Destination.PLAIN,
        APP_NAME,
        "broadcast",
        "public_channel"
    )
    broadcast_destination.set_packet_callback(bpacket_callback)

    announce_handler = LCOMMAnnounceHandler(aspect_filter=None)
    RNS.Transport.register_announce_handler(announce_handler)
    router.announce(my_destination.hash)
    router.register_delivery_callback(msg_callback)
    
    update_contacts()
    return my_destination, router, reticulum, broadcast_destination

def announce_loop(my_destination):
    while True:
        time.sleep(ANNOUNCE_INTERVAL)
        my_destination.announce()
        RNS.log("Sent announce from "+RNS.prettyhexrep(my_destination.hash))

class LCOMMAnnounceHandler():
    def __init__(self, aspect_filter=None):
        self.aspect_filter = aspect_filter
    
    def received_announce(self, destination_hash, announced_identity, app_data):
        global contacts
        hex_hash = destination_hash.hex().lower()
        exs = False
        try:
            name = app_data.decode("utf-8")
        except Exception as e:
            RNS.log(f"[WARN] Failed to decode announce name: {e}")
            name = "Unknown"

        try:
            identity_hash = announced_identity.hash.hex().lower()
            add_identity(identity_hash, hex_hash, name, name)
        except:
            exs = True

        update_contacts()

def announce_myself(my_destination, router):
    my_destination.announce(app_data=DISPLAY_NAME.encode("utf-8"))
    RNS.log("Sent announce from "+RNS.prettyhexrep(my_destination.hash))

def resolve_destination(hex_hash):
    pri_bytes = bytes.fromhex(hex_hash)
    if not RNS.Transport.has_path(pri_bytes):
        RNS.Transport.request_path(pri_bytes)
        while not RNS.Transport.has_path(pri_bytes):
            time.sleep(0.2)
    recipient = RNS.Identity.recall(pri_bytes)
    
    return RNS.Destination(recipient, RNS.Destination.OUT, RNS.Destination.SINGLE, "lxmf", "delivery")

def send_voicemail(wav_path, my_destination, dest_hash):
    global DISPLAY_NAME
    try:
        msg = audio.create_lxmf_audio_message(
            destination=resolve_destination(dest_hash),
            source=my_destination,
            input_wav=wav_path,
            title=f"Voicemail from {DISPLAY_NAME}",
            codec="codec2",
            bitrate = 1200
        )
        if msg:
            router.handle_outbound(msg)
        else:
            raise Exception("Failed to build LXMF message")
    except Exception as e:
        pass

def broadcast_msg(broadcast_destination, text):
    data = text.encode("utf-8")
    packet = RNS.Packet(broadcast_destination, data)
    packet.send()
    log_msg_send("None", text)

def bpacket_callback(data, packet):
    text = data.decode("utf-8")
    log_msg_recv("None", text)

def update_contacts():
    global contacts
    db_entries = get_all_id()
    existing_hashes = {c.get("identity_hash") for c in contacts}

    for row in db_entries:
        rns_hash = row["rnsHash"]
        if rns_hash not in existing_hashes:
            contacts.append({
                "name": row["name"],
                "identity_hash": row["rnsHash"],
                "delivery_hash": row["lxmfHash"],
                "hash": row["lxmfHash"]
            })

def send_msg(router, destination, source, content):
    msg = LXM(
        destination,
        source,
        content,
        "LXMF Message", # random title for now
        desired_method=LXMF.LXMessage.DIRECT,
        include_ticket=True
    )

    router.handle_outbound(msg)

def msg_callback(message):
    global router, my_destination
    hex_hash = message.source_hash.hex().lower()
    #print(hex_hash, str(message.content_as_string()))
    text = str(message.content_as_string())
    log_msg_recv(hex_hash, text)
    #log_msg_recv(RNS.prettyhexrep(message.source_hash),str(message.content_as_string()))

