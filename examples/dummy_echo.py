import time
import RNS
import LXMF

# Setup
storage_path = "./lxmf_echo_storage"
required_stamp_cost = 8
enforce_stamps = False

# Callback for received messages
def on_message_received(message):
    try:
        sender = message.get_source()
        content = message.content.decode("utf-8")

        print(f"[EchoBot] Received from {sender}: {content}")

        reply = LXMF.LXMessage(
            destination = message.source,
            source = my_lxmf_destination,
            content = f"Echo: {content}",
            title = "Echo Reply",
            desired_method = LXMF.LXMessage.DIRECT,
            include_ticket = True
        )
        router.handle_outbound(reply)
        print("[EchoBot] Replied.")
    except Exception as e:
        print("[EchoBot] Error handling message:", e)

# Init Reticulum and LXMF
RNS.Reticulum()
router = LXMF.LXMRouter(storagepath=storage_path, enforce_stamps=enforce_stamps)

identity = RNS.Identity()
my_lxmf_destination = router.register_delivery_identity(
    identity,
    display_name="EchoBot",
    stamp_cost=required_stamp_cost
)

router.register_delivery_callback(on_message_received)

# Show address
print("[EchoBot] Ready. Destination hash:")
print(" ", RNS.prettyhexrep(my_lxmf_destination.hash))

# Keep alive
while True:
    time.sleep(1)
