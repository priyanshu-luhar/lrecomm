import curses
import textwrap
from database_utils import get_messages
from database_utils import log_msg_send

WIDTH = 70
FILLCHAR = " "
SCROLL_STEP = 1

def show_messages(stdscr, identity_hash, NAME):
    curses.curs_set(1)
    stdscr.clear()
    curses.echo()

    height, width = stdscr.getmaxyx()
    input_win_height = 8
    content_height = height - input_win_height - 5

    msg = get_messages(identity_hash)

    # Build wrapped and aligned message lines
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
    scroll_pos = max(0, total_lines - content_height)

    while True:
        stdscr.clear()

        # Header
        stdscr.addstr(0, 0, "-" * width)
        stdscr.addstr(1, (width - len(NAME)) // 2, NAME)
        stdscr.addstr(2, 0, "-" * width)

        # Message view
        view_lines = formatted_lines[scroll_pos:scroll_pos + content_height]
        for idx, line in enumerate(view_lines):
            stdscr.addstr(3 + idx, 0, line[:width])  # Clip long lines
            stdscr.addstr(3 + idx, 0, "")

        # Input line
        stdscr.addstr(height - input_win_height - 2, 0, "-" * width)
        stdscr.addstr(height - input_win_height - 1, 0, "[type \"quit\" and press ENTER to exit] OR [press ENTER with no input to refresh for messages]")
        stdscr.addstr(height - input_win_height, 0, "Type your message: ")
        stdscr.clrtoeol()
        stdscr.refresh()

        # Get user input char by char to handle scroll keys
        win = curses.newwin(1, width - len("Type your message: ") - 1, height - input_win_height, len("Type your message: "))
        curses.curs_set(1)
        box = ""
        while True:
            key = stdscr.getch()
            if key == curses.KEY_UP:
                scroll_pos = max(0, scroll_pos - SCROLL_STEP)
                break
            elif key == curses.KEY_DOWN:
                scroll_pos = min(total_lines - content_height, scroll_pos + SCROLL_STEP)
                break
            elif key == curses.KEY_BACKSPACE or key == 127:
                box = box[:-1]
                win.clear()
                win.addstr(0, 0, box)
                win.refresh()
            elif key == curses.KEY_ENTER or key in [10, 13]:
                user_input = box.strip()
                stdscr.refresh()
                return user_input
            elif 32 <= key <= 126:  # Printable characters
                box += chr(key)
                win.addstr(0, len(box) - 1, chr(key))
                win.refresh()
