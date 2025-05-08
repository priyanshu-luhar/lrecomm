import os
from database_utils import *
from datetime import datetime
import subprocess
import curses
from globals import *

def save_file(fields, hex_hash, output_dir="../str/files/received", output_path=None):
    try:
        if 9 not in fields:
            return None, 0

        file_field = fields[9]
        if not isinstance(file_field, list) or len(file_field) < 2:
            return None, 0

        mode_code = file_field[0]
        file_data = file_field[1]

        base_name = f"{int(time.time())}_file_{hex_hash}"
        if output_path:
            output_file_path = output_path
            output_dir_final = os.path.dirname(output_path)
        else:
            output_dir_final = output_dir
            output_file_path = os.path.join(output_dir_final, f"{base_name}.file")

        
        return output_file_path


    except Exception as e:
        return None

def get_manual_file_path(stdscr):
    curses.echo()
    stdscr.clear()
    stdscr.addstr(0, 0, "Enter full file path:")
    stdscr.refresh()

    path = stdscr.getstr(1, 0, 512).decode("utf-8")
    curses.noecho()

    if os.path.isfile(path):
        return os.path.abspath(path)
    else:
        stdscr.addstr(3, 0, "Invalid file path. Press any key to continue.")
        stdscr.refresh()
        stdscr.getch()
        return None
