import pyaudio
import wave
import keyboard
import os
from database_utils import log_vm_send
from database_utils import get_voicemail
from datetime import datetime

def record_voicemail(stdsrc, identity_hash, save_folder="../str/voicemails/sent", rate=8000, chunk=1024, channels=1):
    format = pyaudio.paInt16
    frames = []

    os.makedirs(save_folder, exist_ok=True)

    p = pyaudio.PyAudio()
    stream = p.open(format=format,
                    channels=channels,
                    rate=rate,
                    input=True,
                    frames_per_buffer=chunk)

    print("Recording started. Press 'Esc' to stop.")
    try:
        while True:
            if keyboard.is_pressed('Esc'):
                break
            data = stream.read(chunk)
            frames.append(data)
    except Exception as e:
        print(f"Error during recording: {e}")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

    print("Recording finished.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{identity_hash}.wav"
    filepath = os.path.join(save_folder, filename)

    # Save the recorded frames to a WAV file
    with wave.open(filepath, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(p.get_sample_size(format))
        wf.setframerate(rate)
        wf.writeframes(b''.join(frames))

    print(f"Voicemail saved to: {filepath}")
    log_vm_send(identity_hash, filepath)
    return filepath

def play_voicemail(vm_id):
    file_path_list = get_voicemail(vm_id)
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    # Open the WAV file
    wf = wave.open(file_path, 'rb')

    # Set up PyAudio stream based on the file's properties
    p = pyaudio.PyAudio()
    stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True)

    # Read and play audio in chunks
    chunk = 1024
    data = wf.readframes(chunk)
    print(f"Playing: {file_path}")
    while data:
        stream.write(data)
        data = wf.readframes(chunk)

    # Cleanup
    stream.stop_stream()
    stream.close()
    p.terminate()
    wf.close()
    print("Playback finished.")


