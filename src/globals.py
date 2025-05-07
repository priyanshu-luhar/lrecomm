import threading

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
DISPLAY_NAME = "gonna"


refresh_needed = threading.Event()
my_destination, router, reticulum, broadcast_destination = None, None, None, None
