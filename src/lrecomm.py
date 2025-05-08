import os
import sys
import RNS
import LXMF
import time
import curses
import threading
import signal

from database_utils import *
from voicemail_utils import *
from reticulum_utils import *
# from audio_call import *
from message_utils import *
from globals import *

from datetime import datetime as dt
from LXMF import LXMessage as LXM
from LXST.Sources import LineSource
from LXST.Sinks import LineSink
from voice import ReticulumTelephone
from wav_sink import FileSink
from audio_call import setup_audio_call

RNS.logfile = "../logs/rns.log"
RNS.loglevel = RNS.LOG_EXTREME
RNS.logdest = RNS.LOG_FILE


def draw_box(stdscr, title, options, descriptions, current_idx):
    stdscr.clear()
    height, width = stdscr.getmaxyx()
    box_height = len(options) + 4
    box_width = max(len(f"[{k}] {descriptions[k]}") for k in options) + 6
    start_y = (height - box_height) // 2
    start_x = (width - box_width) // 2

    # Top & bottom borders
    stdscr.addstr(start_y, start_x, "┌" + "─" * (box_width - 2) + "┐")
    stdscr.addstr(start_y + box_height - 1, start_x, "└" + "─" * (box_width - 2) + "┘")

    # Side borders
    for y in range(1, box_height - 1):
        stdscr.addstr(start_y + y, start_x, "│")
        stdscr.addstr(start_y + y, start_x + box_width - 1, "│")

    # Title
    title_x = start_x + (box_width - len(title)) // 2
    stdscr.addstr(start_y + 1, title_x, title, curses.A_BOLD)

    # Menu items
    for idx, key in enumerate(options):
        text = descriptions[key]
        line = f"│ {text.ljust(box_width - 4)} │"
        y = start_y + 2 + idx
        attr = curses.A_REVERSE if idx == current_idx else curses.A_NORMAL
        stdscr.addstr(y, start_x, line, attr)

    stdscr.refresh()

def get_user_input(stdscr, prompt):
    curses.echo()
    stdscr.clear()
    stdscr.addstr(0, 0, prompt)
    stdscr.refresh()
    input_str = stdscr.getstr(1, 0, 200).decode("utf-8")
    curses.noecho()
    return input_str


def handle_menu(stdscr, title, descriptions):
    global telephone
    options = list(descriptions.keys())
    current_idx = 0

    stdscr.nodelay(True)  # Non-blocking mode
    stdscr.clear()

    base_title = title  # Keep the original title static
    dynamic_title = f"{base_title} [{telephone.status_text}]"
    draw_box(stdscr, dynamic_title, options, descriptions, current_idx)
    try:
        while True:
            dynamic_title = f"{base_title} [{telephone.status_text}]"

            if refresh_needed.is_set():
                draw_box(stdscr, dynamic_title, options, descriptions, current_idx)
                refresh_needed.clear()

            key = stdscr.getch()
            if key == -1:
                time.sleep(0.1)
                continue

            if key == curses.KEY_UP:
                current_idx = (current_idx - 1) % len(options)
                draw_box(stdscr, dynamic_title, options, descriptions, current_idx)
            elif key == curses.KEY_DOWN:
                current_idx = (current_idx + 1) % len(options)
                draw_box(stdscr, dynamic_title, options, descriptions, current_idx)
            elif key in [curses.KEY_ENTER, 10, 13]:
                return options[current_idx]
            elif key == 27:  # ESC
                return "back"
    finally:
        stdscr.nodelay(False)


def show_menu(stdscr):
    global contacts, my_destination, router, reticulum, broadcast_destination, telephone
    curses.curs_set(0)
    stdscr.keypad(True)
    # threading.Thread(target=background_refresh, args=(stdscr,), daemon=True).start()

    main_menu = {
        "messages": "Messages",
        "voicemail": "Voicemail",
        "audio": "Audio Call",
        "files": "Files",
        "announce": "Announce",
        "broadcast": "Broadcast",
        "web": "Web",
        "sip": "SIP",
        "mayday": "MAYDAY [Emergency Broadcast]",
        "q": "Quit"
    }

    while True:
        title = f"LRECOMM"
        selected = handle_menu(stdscr, title, main_menu)

        if selected == "q":
            break

        elif selected == "messages":
            contact_menu = {str(i): f"{c['name']} " for i, c in enumerate(contacts)}
            contact_menu["back"] = "Back to Main Menu"

            contact_selected = handle_menu(stdscr, "Send Message To", contact_menu)

            if contact_selected in contact_menu and contact_selected != "back":
                recipient = contacts[int(contact_selected)]
                while True:
                    user_input = show_messages(stdscr, recipient['hash'], recipient['name'])

                    if user_input == "quit":
                        break
                    elif user_input == "":
                        pass
                    else:
                        dest = resolve_destination(recipient['hash'])
                        send_msg(router, dest, my_destination, user_input)
                        log_msg_send(recipient['hash'], user_input)
        elif selected == "voicemail":
            vm_menu = {}
            vm_menu["send"] = "Send a Voicemail"
            vm_menu["unread"] = "Voicemails Received: Unread"
            vm_menu["recv"] = "Previous Voicemails Received"
            vm_menu["sent"] = "Voicemails Sent"
            vm_menu["back"] = "Back to Main Menu"

            vm_selected = handle_menu(stdscr, "Voicemail", vm_menu)

            if vm_selected == "send":
                send_vm_menu = {str(i): f"{c['name']} " for i, c in enumerate(contacts)}
                send_vm_menu["back"] = "Back to Voicemail Menu"

                send_vm_selected = handle_menu(stdscr, "Send Voicemail To", send_vm_menu)
                if send_vm_selected in send_vm_menu and send_vm_selected != "back":
                    recipient = contacts[int(send_vm_selected)]
                    vm_filepath = record_voicemail(stdscr, recipient["hash"])
                    log_vm_send(recipient["hash"], vm_filepath)
                    
                    # todo, gonna add a function call to send audio file to the recipient hash
                    
                    stdscr.clear()
                    stdscr.addstr(0, 0, f"To: {recipient['name']} [{recipient['hash']}]", curses.A_BOLD)
                    stdscr.addstr(1, 0, f"Voicemail Path: {vm_filepath}")
                    stdscr.addstr(2, 0, f"Logged into the database")
                    stdscr.refresh()
                    time.sleep(2)

            elif vm_selected == "unread":
                unread_vm = get_unread_voicemails()
                unread_vm_menu = {str(i): f"{c['wavpath']} " for i, c in enumerate(unread_vm)}
                unread_vm_menu["back"] = "Back to Voicemail Menu"
            elif vm_selected == "recv":
                recv_vm = get_unread_voicemails()
                recv_vm_menu = {str(i): f"{c['wavpath']} " for i, c in enumerate(recv_vm)}
                recv_vm_menu["back"] = "Back to Voicemail Menu"

            elif vm_selected == "sent":
                tump = 1
            else:
                tump = 1
                # Imma do nothin
        elif selected == "announce":
            announce_myself(my_destination, router)
            stdscr.clear()
            stdscr.addstr(0, 0, f"Announced myself with hash: {my_destination.hash.hex()}", curses.A_BOLD)
            stdscr.refresh()
            time.sleep(1)
        elif selected == "broadcast":
            while True:
                user_input = show_messages(stdscr, "None", "Broadcast")
                if user_input == "quit":
                    break
                elif user_input == "":
                    pass
                else:
                    broadcast_msg(broadcast_destination, user_input)
        elif selected == "audio":
            audio_menu = {}
            # if telephone.is_in_call:
            if not telephone.is_available:
                audio_menu["hangup"] = "Hang Up"
            else:
                audio_menu["call"] = "Place an Audio Call"
            audio_menu["back"] = "Back to Main Menu"

            audio_selected = handle_menu(stdscr, "Audio Call", audio_menu)

            if audio_selected == "call":
                call_menu = {str(i): f"{c['name']}" for i, c in enumerate(contacts)}
                call_menu["back"] = "Back to Audio Menu"

                selected_contact = handle_menu(stdscr, "Call Contact", call_menu)
                if selected_contact != "back":
                    recipient = contacts[int(selected_contact)]

                    RNS.log(f"Calling {recipient['name']} with delivery_hash {recipient['delivery_hash']}", RNS.LOG_DEBUG)
                    try:
                        peer_bytes = bytes.fromhex(recipient["delivery_hash"])
                        peer_identity = RNS.Identity.recall(peer_bytes)
                        if not peer_identity:
                            RNS.Transport.request_path(peer_bytes)
                            time.sleep(1)
                            peer_identity = RNS.Identity.recall(peer_bytes)

                        if peer_identity:
                            telephone.call(peer_identity)
                            stdscr.clear()
                            stdscr.addstr(0, 0, f"Dialing {recipient['name']}...", curses.A_BOLD)
                            stdscr.refresh()
                            time.sleep(3)
                        else:
                            stdscr.addstr(0, 0, f"Could not resolve identity", curses.A_BOLD)
                            stdscr.refresh()
                            time.sleep(2)
                    except Exception as e:
                        stdscr.addstr(0, 0, f"Call failed: {e}", curses.A_BOLD)
                        stdscr.refresh()
                        time.sleep(2)
            elif audio_selected == "hangup":
                telephone.hangup()
                stdscr.clear()
                stdscr.addstr(0, 0, "Call ended", curses.A_BOLD)
                stdscr.refresh()
                time.sleep(2)

        else:
            stdscr.clear()
            msg = f"You selected: {main_menu[selected]}"
            stdscr.addstr(0, 0, msg, curses.A_BOLD)
            stdscr.refresh()
            time.sleep(2)

# def background_refresh(interval=0.5):
#     # pass
#     while True:
#         time.sleep(interval)
#         refresh_needed.set()

def run_menu():
    curses.wrapper(show_menu)
    
def shutdown():
    # print("[CLEANUP] Hanging up and shutting down RNS...")
    RNS.log("Hanging up and shutting down RNS...", RNS.LOG_DEBUG)
    global telephone
    try:
        if telephone.is_in_call:
            RNS.log("Hanging up call...", RNS.LOG_DEBUG)
            telephone.hangup()
        telephone.stop()     # Tears down threads, releases devices
    except Exception as e:
        RNS.log(f"[ERROR] During telephone shutdown: {e}", RNS.LOG_ERROR)
        # print(f"[ERROR] During telephone shutdown: {e}")

    RNS.Transport.detach_interfaces()
    RNS.Transport.identity = None
    RNS.reticulum = None


# sigint handler
def signal_handler(signum, frame):
    # print(f"[INFO] Received signal {signum}, shutting down...")
    RNS.log(f"Received {signum} signal shutting down...", RNS.LOG_ERROR)
    shutdown()
    sys.exit(0)
# Register the signal handler

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main():
    global my_destination, router, reticulum, broadcast_destination, telephone
    my_destination, router, reticulum, broadcast_destination = rns_setup("../.reticulum")
    id = load_identity()
    # telephone = setup_audio_call()
    speaker = LineSink()
    microphone = LineSource()
    output_directory = "../audio_out"
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)
    recording_path = os.path.join(output_directory, "voicemail.wav") 

    file_sink = FileSink(recording_path, samplerate=8000)
    # telephone = ReticulumTelephone(id, microphone=microphone, auto_answer=0.5, receive_sink=file_sink)
    telephone = ReticulumTelephone(id, speaker=speaker, microphone=microphone, auto_answer=0.5)
    telephone.announce()


    run_menu()
    shutdown()

if __name__ == "__main__":
    main()

