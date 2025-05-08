import os
import RNS
import sys
import LXMF
import json

from LXMF import LXMessage as LXM
from database_utils import *
from voicemail_utils import *
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
    my_destination.announce(app_data=DISPLAY_NAME.encode("utf-8"))
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

# Receiving
######################################################################################

def msg_callback(message):
    global router, my_destination
    hex_hash = message.source_hash.hex().lower()
    text = str(message.content_as_string())

    if message.title_as_string() == "Message":
        log_msg_recv(hex_hash, text)
    elif message.title_as_string() == "Voicemail":
        decoded_path = save_and_decode_audio(message.fields)
        log_vm_recv(hex_hash, decoded_path)
    elif message.title_as_string() == "File":
        try:
            attachments = message.fields.get(LXMF.FIELD_FILE_ATTACHMENTS)
            if attachments and isinstance(attachments, list):
                save_dir = "../str/files/received"
                os.makedirs(save_dir, exist_ok=True)

                for attachment in attachments:
                    if len(attachment) == 2:
                        filename, file_bytes = attachment
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        safe_name = f"{timestamp}_{filename}"
                        file_path = os.path.join(save_dir, safe_name)

                        with open(file_path, "wb") as f:
                            f.write(file_bytes)

                        log_file_recv(hex_hash, file_path)
                    else:
                        pass
            else:
                pass
        except Exception as e:
            print(f"[!] Error saving received file: {e}")
    else:
        pass

# Sending
######################################################################################

def send_msg(router, destination, source, content):
    msg = LXM(
        destination,
        source,
        content,
        "Message", # random title for now
        desired_method=LXMF.LXMessage.DIRECT,
        include_ticket=True
    )

    router.handle_outbound(msg)

def send_vm(wavpath, my_destination, dest_hash, router):
    global DISPLAY_NAME
    try:
        destination = resolve_destination(dest_hash)
        
        mode_code, audio_bytes = convert_audio_to_bytes(wavpath) 

        msg = LXM(
            destination,
            my_destination,
            f"Voicemail from {DISPLAY_NAME}", # content
            "Voicemail", # title
            desired_method=LXMF.LXMessage.DIRECT,
            include_ticket=True
        )
        msg.fields[7] = [mode_code, audio_bytes]
        if msg:
            router.handle_outbound(msg)
        else:
            raise Exception("Failed to build LXMF message")
    except Exception as e:
        print(f"Error: {e}")
        pass

def send_file(filepath, my_destination, dest_hash, router):
    global DISPLAY_NAME
    try:
        destination = resolve_destination(dest_hash)
        filename = os.path.basename(filepath)
        
        with open(filepath, "rb") as f:
            file_bytes = f.read()
        
        msg = LXM(
            destination,
            my_destination,
            f"{DISPLAY_NAME}_{filename}", # content
            "File", # title
            desired_method=LXMF.LXMessage.DIRECT,
            include_ticket=True
        )
        msg.fields[LXMF.FIELD_FILE_ATTACHMENTS] = [[filename, file_bytes]] 
        
        if msg:
            router.handle_outbound(msg)
        else:
            raise Exception("Failed to build LXMF message")
    except Exception as e:
        print(f"Error: {e}")
        pass
