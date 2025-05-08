import sqlite3
import os
import time

DB_PATH = os.path.join("..", "dbs", "lrecomm_local.db")

def add_identity(rns_hash, lxmf_hash, name, username):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO identity (rnsHash, lxmfHash, name, username)
            VALUES (?, ?, ?, ?)
        """, (rns_hash, lxmf_hash, name, username))
        conn.commit()

def get_all_id():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT rnsHash, name FROM identity;")
        return c.fetchall()

def log_msg_send(receiver_hash, content):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO msg_sent (receiverHash, content)
            VALUES (?, ?)
        """, (receiver_hash, content))
        conn.commit()

def log_msg_recv(sender_hash, content):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO msg_recv (senderHash, content)
            VALUES (?, ?)
        """, (sender_hash, content))
        conn.commit()

def log_vm_send(receiver_hash, wavpath):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO vm_sent (receiverHash, wavpath)
            VALUES (?, ?)
        """, (receiver_hash, wavpath))
        conn.commit()

def log_vm_recv(sender_hash, wavpath):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO vm_recv (senderHash, wavpath)
            VALUES (?, ?)
        """, (sender_hash, wavpath))
        conn.commit()

def log_file_send(receiver_hash, filepath):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO file_sent (receiverHash, filepath)
            VALUES (?, ?)
        """, (receiver_hash, filepath))
        conn.commit()

def log_file_recv(sender_hash, filepath):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO file_recv (senderHash, filepath)
            VALUES (?, ?)
        """, (sender_hash, filepath))
        conn.commit()

def get_messages(identity_hash):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT content, time, align FROM msg_sent WHERE receiverHash = ?
            UNION
            SELECT content, time, align FROM msg_recv WHERE senderHash = ?
            ORDER BY time;
        """, (identity_hash, identity_hash))
        return c.fetchall()

def get_voicemail(vm_id):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT wavpath FROM vm_recv WHERE vmID = ?;", (vm_id,))
        return c.fetchall()

def get_all_voicemails(direction):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        if direction == "sent":
            c.execute("SELECT wavpath, time FROM vm_sent ORDER BY time;")
        elif direction == "recv":
            c.execute("SELECT wavpath, time FROM vm_recv ORDER BY time;")
        else:
            return []
        return c.fetchall()

def get_unread_voicemails():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT wavpath, time, senderHash FROM vm_recv WHERE unread = 1 ORDER BY time;")
        return c.fetchall()

def get_recv_voicemails():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT wavpath, time, senderHash FROM vm_recv;")
        return c.fetchall()

def get_sent_voicemails():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT wavpath, time, receiverHash FROM vm_sent;")
        return c.fetchall()

def get_all_files(direction):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        if direction == "sent":
            c.execute("SELECT filepath, time FROM file_sent ORDER BY time;")
        elif direction == "recv":
            c.execute("SELECT filepath, time FROM file_recv ORDER BY time;")
        else:
            return []
        return c.fetchall()

def get_recv_files():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT filepath, time, senderHash FROM file_recv;")
        return c.fetchall()

def get_sent_files():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT filepath, time, receiverHash FROM file_sent;")
        return c.fetchall()
