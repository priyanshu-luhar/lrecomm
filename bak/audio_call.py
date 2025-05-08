import os
import time
import logging
from datetime import datetime
from threading import Thread

from LXST.Primitives.Telephony import Telephone
from LXST.Sinks import LineSink
from LXST.Sources import LineSource
from LXST.Codecs import Codec2
from LXST.Pipeline import Pipeline
import RNS

def resolve_destination(hex_hash):
    pri_bytes = bytes.fromhex(hex_hash)
    if not RNS.Transport.has_path(pri_bytes):
        RNS.Transport.request_path(pri_bytes)
        while not RNS.Transport.has_path(pri_bytes):
            time.sleep(0.2)
    recipient = RNS.Identity.recall(pri_bytes)
    return RNS.Destination(recipient, RNS.Destination.OUT, RNS.Destination.SINGLE, "lxmf", "delivery")


class AudioCallHandler:
    def __init__(self, identity, mailbox="7002", inbox_path=None):
        self.telephone = Telephone(identity)
        self.mailbox = mailbox
        self.inbox_path = inbox_path or f"/var/spool/asterisk/voicemail/default/{mailbox}/INBOX"
        self._call_active = False
        logging.debug(f"[AudioCallHandler] Initialized for mailbox {self.mailbox}, inbox at {self.inbox_path}")

    def start_listening(self):
        logging.debug("[AudioCallHandler] Starting call listener thread...")
        Thread(target=self._call_loop, daemon=True).start()

    def _call_loop(self):
        logging.info("[AudioCallHandler] Listener is active and waiting for incoming calls...")
        self.telephone.proxy = self  # Register for signaling events
        while True:
            time.sleep(1)

    def signalling_received(self, signals, source):
        logging.debug(f"[AudioCallHandler] Received signaling: {signals} from {source}")
        if "CALL_REQUEST" in signals and not self._call_active:
            logging.info("[AudioCallHandler] CALL_REQUEST received, answering call...")
            self._call_active = True
            Thread(target=self._handle_call, args=(source,), daemon=True).start()

    def _handle_call(self, source):
        now = int(time.time())
        base_filename = f"msg{now % 10000:04d}"
        wav_path = os.path.join(self.inbox_path, f"{base_filename}.wav")
        txt_path = os.path.join(self.inbox_path, f"{base_filename}.txt")

        os.makedirs(self.inbox_path, exist_ok=True)

        self.telephone.set_speaker(LineSink(wav_path))
        self.telephone.answer()
        logging.info(f"[AudioCallHandler] Call answered. Recording to {wav_path}...")

        while self.telephone.pipeline and self.telephone.pipeline.active:
            time.sleep(1)

        self._call_active = False
        logging.info("[AudioCallHandler] Call ended. Writing metadata...")
        self._create_metadata(txt_path)
        os.chmod(wav_path, 0o660)
        os.chmod(txt_path, 0o660)

    def _create_metadata(self, path, duration=5):
        dt = datetime.now()
        with open(path, "w") as f:
            f.write(f"""{int(time.time())}|{dt.hour}:{dt.minute}|{dt.strftime('%A')}|{dt.strftime('%B')} {dt.day} {dt.year}||callerid=\"\"|duration={duration}\n""")
        logging.debug(f"[AudioCallHandler] Metadata written to {path}")

    def dial(self, destination_hash):
        logging.info(f"[AudioCallHandler] Dialing {destination_hash}...")

        try:
            self.destination = resolve_destination(destination_hash)
        except Exception as e:
            logging.error(f"[AudioCallHandler] Failed to resolve destination: {e}")
            return

        mic = LineSource(target_frame_ms=40)
        speaker = LineSink()
        self.telephone.set_microphone(mic)
        self.telephone.set_speaker(speaker)

        self.telephone.call(self.destination)
        logging.info("[AudioCallHandler] Outgoing call initiated.")

