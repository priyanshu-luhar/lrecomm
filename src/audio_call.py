from wav_sink import FileSink
from LXST.Sinks import LineSink
from LXST.Sources import LineSource
import os
from voice import ReticulumTelephone
from globals import *


def setup_audio_call():
    global telephone
    speaker = LineSink()
    microphone = LineSource()
    output_directory = "../audio_out"
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)
    recording_path = os.path.join(output_directory, "voicemail.wav") 

    file_sink = FileSink(recording_path)
    telephone = ReticulumTelephone(id, speaker=speaker, microphone=microphone, auto_answer=0.5, receive_sink=file_sink)
    telephone.announce()
    return telephone