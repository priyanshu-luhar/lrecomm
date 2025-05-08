import curses
import textwrap
import time
import threading

from globals import *
from database_utils import get_messages
from database_utils import log_msg_send

WIDTH = 70
FILLCHAR = " "
SCROLL_STEP = 1
box = ""


def threaded_input(stdscr, stop_event, scroll_state):
    global box
    box = ""
    stdscr.nodelay(True)

    while not stop_event.is_set():
        key = stdscr.getch()
        if key == -1:
            time.sleep(0.05)
            continue
        elif key in [10, 13]:  # ENTER
            stop_event.set()
            break
        elif key in [curses.KEY_BACKSPACE, 127]:
            box = box[:-1]
        elif key == curses.KEY_UP:
            scroll_state["pos"] = max(0, scroll_state["pos"] - SCROLL_STEP)
        elif key == curses.KEY_DOWN:
            scroll_state["pos"] = min(scroll_state["max"], scroll_state["pos"] + SCROLL_STEP)
        elif 32 <= key <= 126:
            box += chr(key)


def show_messages(stdscr, identity_hash, NAME):
    global box
    box = ""
    stop_event = threading.Event()
    scroll_state = {"pos": 0, "max": 0, "user_scrolled": False, "last_msg_count": 0}

    curses.curs_set(1)
    stdscr.nodelay(True)
    curses.noecho()

    height, width = stdscr.getmaxyx()
    input_win_height = 8
    content_height = height - input_win_height - 5

    # Launch input thread with scroll control
    input_thread = threading.Thread(target=threaded_input, args=(stdscr, stop_event, scroll_state))
    input_thread.start()

    while not stop_event.is_set():
        stdscr.erase()

        # Header
        stdscr.addstr(0, 0, "-" * width)
        stdscr.addstr(1, (width - len(NAME)) // 2, NAME)
        stdscr.addstr(2, 0, "-" * width)

        # Messages
        msg = get_messages(identity_hash)
        formatted_lines = []
        for x in msg:
            wrapped = textwrap.wrap(x[0], WIDTH)
            if x[2] == 1:
                aligned = [line.rjust(width) for line in wrapped]
                aligned.append(x[1].rjust(width))
            else:
                aligned = [line.ljust(width) for line in wrapped]
                aligned.append(x[1].ljust(width))
            formatted_lines.extend(aligned)

        total_lines = len(formatted_lines)
        scroll_state["max"] = max(0, total_lines - content_height)

        # Auto-scroll to bottom if new message arrived and user didn't scroll manually
        if total_lines != scroll_state.get("last_msg_count", 0):
            scroll_state["pos"] = scroll_state["max"]
        scroll_state["last_msg_count"] = total_lines
        scroll_pos = scroll_state["pos"]
        
        view_lines = formatted_lines[scroll_pos:scroll_pos + content_height]
        for idx, line in enumerate(view_lines):
            stdscr.addstr(3 + idx, 0, line[:width])

        # Input
        stdscr.addstr(height - input_win_height - 2, 0, "-" * width)
        stdscr.addstr(height - input_win_height - 1, 0, "[Type message + ENTER to send | Use ↑↓ to scroll]")
        stdscr.addstr(height - input_win_height, 0, "Type your message: ")
        stdscr.addstr(height - input_win_height, len("Type your message: "), box[:width - 20])
        stdscr.refresh()

        time.sleep(0.1)

    input_thread.join()
    return box.strip()

