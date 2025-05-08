import threading

'''
contacts = [
    {"hash": "ABC123", "name": "Alice"},
    {"hash": "DEF456", "name": "Bob"},
    {"hash": "GHI789", "name": "Charlie"}
]
'''
contacts = []

my_destination = None
broadcast_destination = None
reticulum = None
router = None

APP_NAME = "lrecomm"
ANNOUNCE_INTERVAL = 60
IDENTITY_PATH = "../dbs/my_identity"
STORAGE_DIR = "../dbs/lxmf"
STAMP_COST = 1
DISPLAY_NAME = "Cheeky Monkey"


refresh_needed = threading.Event()
my_destination, router, reticulum, broadcast_destination = None, None, None, None

IS_SIP = False
