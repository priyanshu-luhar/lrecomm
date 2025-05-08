import wave
import numpy as np
import threading
import time
from LXST.Sinks import Sink
import RNS

class FileSink(Sink):
    def __init__(self, output_path, samplerate=8000, channels=1):
        self.output_path = output_path
        self.samplerate = samplerate
        self.channels = channels
        self.frames = []
        self.frame_buffer = []
        self.buffer_lock = threading.Lock()
        self.should_run = False
        RNS.log(f"FileSink initialized with output path: {self.output_path}", RNS.LOG_DEBUG)

    def can_receive(self, from_source=None):
        return True

    def handle_frame(self, frame, source=None):
        RNS.log(f"FileSink got frame: type={type(frame)}, shape={getattr(frame, 'shape', None)}, dtype={getattr(frame, 'dtype', None)}", RNS.LOG_DEBUG)
        with self.buffer_lock:
            self.frame_buffer.append(frame)

    def start(self):
        RNS.log("FileSink worker starting", RNS.LOG_DEBUG)
        self.should_run = True
        threading.Thread(target=self.__sink_worker, daemon=True).start()

    def stop(self):
        RNS.log("FileSink worker stopping", RNS.LOG_DEBUG)
        self.should_run = False
        time.sleep(0.5)  # Give time for thread to finish

    def __sink_worker(self):
        RNS.log("FileSink worker started", RNS.LOG_DEBUG)
        while self.should_run or self.frame_buffer:
            with self.buffer_lock:
                if self.frame_buffer:
                    frame = self.frame_buffer.pop(0)
                    self.frames.append(frame)
            time.sleep(0.01)
        RNS.log("FileSink worker stopped", RNS.LOG_DEBUG)

    def write_wav(self):
        RNS.log(f"Writing WAV file to {self.output_path}", RNS.LOG_DEBUG)
        self.frames = [f for f in self.frames if np.max(np.abs(f)) > 0.01]
        with wave.open(self.output_path, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit audio
            wf.setframerate(self.samplerate)
            for frame in self.frames:
                # Convert bytes to int16 if necessary
                if isinstance(frame, bytes):
                    frame = np.frombuffer(frame, dtype=np.int16)

                # Convert float32 to int16 if necessary
                if frame.dtype != np.int16:
                    frame = np.clip(frame, -1.0, 1.0)
                    frame = (frame * 32767).astype(np.int16)

                # Flatten multi-channel (e.g., shape (1915,1)) to 1D
                frame = frame.flatten()
                wf.writeframes(frame.tobytes())

        RNS.log(f"WAV file written to {self.output_path}", RNS.LOG_DEBUG)


