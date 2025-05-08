import os
import sys
import RNS
import LXMF
import time
import curses
import threading
import subprocess

from database_utils import *
from voicemail_utils import *
from reticulum_utils import *
from message_utils import *
from file_utils import *
from globals import *

from datetime import datetime as dt
from LXMF import LXMessage as LXM


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
    options = list(descriptions.keys())
    current_idx = 0

    while True:
        draw_box(stdscr, title, options, descriptions, current_idx)
        key = stdscr.getch()

        if key == curses.KEY_UP:
            current_idx = (current_idx - 1) % len(options)
        elif key == curses.KEY_DOWN:
            current_idx = (current_idx + 1) % len(options)
        elif key in [curses.KEY_ENTER, 10, 13]:
            return options[current_idx]
        elif key == 27:
            return "back"

def show_menu(stdscr):
    global contacts, my_destination
    curses.curs_set(0)
    stdscr.keypad(True)

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
        selected = handle_menu(stdscr, "LRECOMM", main_menu)

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
                    
                    # records a voice message in wav format and returns filepath
                    vm_filepath = record_voicemail(stdscr, recipient["hash"])
                    #vm_filepath = "../str/voicemails/received/demo.wav"
                    send_vm(vm_filepath, my_destination, recipient["hash"], router)
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
                recv_vm = get_recv_voicemails()
                recv_vm_menu = {str(i): f"{c[0]} " for i, c in enumerate(recv_vm)}
                recv_vm_menu["back"] = "Back to Voicemail Menu"
                recv_vm_selected = handle_menu(stdscr, "Received Voicemails", recv_vm_menu)
                
                if recv_vm_selected:
                    play_demo_voicemail("../str/voicemails/received/demo.wav")

            elif vm_selected == "sent":
                pass
            else:
                pass
                # Imma do nothin
        elif selected == "files":
            file_menu = {}
            file_menu["send"] = "Send a File"
            file_menu["recv"] = "Files Received"
            file_menu["sent"] = "Files Sent"
            file_menu["back"] = "Back to Main Menu"

            file_selected = handle_menu(stdscr, "File", file_menu)

            if file_selected == "send":
                send_file_menu = {str(i): f"{c['name']} " for i, c in enumerate(contacts)}
                send_file_menu["back"] = "Back to File Menu"

                send_file_selected = handle_menu(stdscr, "Send File To", send_file_menu)
                if send_file_selected in send_file_menu and send_file_selected != "back":
                    recipient = contacts[int(send_file_selected)]
                    
                    file_filepath = get_manual_file_path(stdscr)
                    
                    send_file(file_filepath, my_destination, recipient["hash"], router)
                    time.sleep(5)
                    
                    log_file_send(recipient["hash"], file_filepath)
                    
                    stdscr.clear()
                    stdscr.addstr(0, 0, f"To: {recipient['name']} [{recipient['hash']}]", curses.A_BOLD)
                    stdscr.addstr(1, 0, f"File Path: {file_filepath}")
                    stdscr.addstr(2, 0, f"Logged into the database")
                    stdscr.refresh()
                    time.sleep(2)

            elif file_selected == "recv":
                pass
            elif file_selected == "sent":
                pass
            else:
                pass
                # Imma do nothing
        elif selected == "sip":
            sip_menu = {}
            sip_menu["issip"] = "SIP gateway"
            sip_menu["notsip"] = "Normal Client"
            sip_menu["back"] = "Back to Main Menu"

            if IS_SIP:
                sip_title = "This is a SIP"
                sip_selected = handle_menu(stdscr, sip_title, sip_menu)
            else:
                sip_title = "This is a CLIENT"
                sip_selected = handle_menu(stdscr, sip_title, sip_menu)
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
        else:
            stdscr.clear()
            msg = f"You selected: {main_menu[selected]}"
            stdscr.addstr(0, 0, msg, curses.A_BOLD)
            stdscr.refresh()
            time.sleep(2)

def run_menu():
    curses.wrapper(show_menu)
    
def shutdown():
    print("[CLEANUP] Shutting down RNS...")
    RNS.Transport.detach_interfaces()
    RNS.Transport.identity = None
    RNS.reticulum = None

if __name__ == "__main__":
     my_destination, router, reticulum, broadcast_destination = rns_setup("../.reticulum")

     try:
        run_menu()
     except Exception as e:
        print(f'We encountered an error: {e}')
     finally:
        shutdown()
