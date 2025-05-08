import pyaudio
import wave
import keyboard
import os
from database_utils import *
from datetime import datetime
import subprocess
import curses
import RNS

def record_voicemail(stdscr, identity_hash, save_folder="../str/voicemails/sent", rate=8000, chunk=1024, channels=1):
    format = pyaudio.paInt16
    frames = []

    os.makedirs(save_folder, exist_ok=True)

    p = pyaudio.PyAudio()
    stream = p.open(format=format,
                    channels=channels,
                    rate=rate,
                    input=True,
                    frames_per_buffer=chunk)

    stdscr.clear()
    msg = f"Recording started. Press 'Esc' to stop."
    stdscr.addstr(0, 0, msg, curses.A_BOLD)
    stdscr.refresh()
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


    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{identity_hash}.wav"
    filepath = os.path.join(save_folder, filename)

    # Save the recorded frames to a WAV file
    with wave.open(filepath, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(p.get_sample_size(format))
        wf.setframerate(rate)
        wf.writeframes(b''.join(frames))

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

def play_demo_voicemail(file_path):
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



def convert_audio_to_bytes(input_wav, codec="codec2", bitrate=1200):
    """
    Converts an input WAV file to encoded audio bytes for either Codec2 or Opus.
    Returns (mode_code, audio_bytes).
    """
    try:
        if codec == "codec2":
            raw_path = input_wav.replace(".wav", ".raw")
            c2_path = input_wav.replace(".wav", f"_{bitrate}.c2")

            subprocess.run([
                "ffmpeg", "-y", "-i", input_wav,
                "-f", "s16le", "-ar", bitrate, "-ac", "1", raw_path
            ], check=True)

            subprocess.run([
                "c2enc", str(bitrate), raw_path, c2_path
            ], check=True)

            with open(c2_path, "rb") as f:
                return {1200: 4, 3200: 9}.get(bitrate, 4), f.read()

        elif codec == "opus":
            opus_path = input_wav.replace(".wav", ".opus")
            subprocess.run([
                "ffmpeg", "-y", "-i", input_wav,
                "-c:a", "libopus", "-ar", "16000", "-ac", "1", opus_path
            ], check=True)

            with open(opus_path, "rb") as f:
                return 16, f.read()

    except Exception as e:
        return None, None

def encode_audio_to_codec2(input_path, output_path, bitrate=1200):
    try:
        raw_path = output_path.replace(".c2", ".raw")
        # Convert input file to 8kHz, mono, 16-bit PCM raw format
        subprocess.run([
            "ffmpeg", "-y", "-i", input_path,
            "-f", "s16le", "-ar", bitrate, "-ac", "1", raw_path
        ], check=True)

        # Encode raw audio to Codec2
        subprocess.run([
            "c2enc", str(bitrate), raw_path, output_path
        ], check=True)

        return output_path
    except Exception as e:
        return None

def decode_codec2_to_wav(input_path, output_wav_path, bitrate=1200):
    try:
        raw_path = input_path.replace(".c2", "_decoded.raw")

        # Decode .c2 to raw
        subprocess.run([
            "c2dec", str(bitrate), input_path, raw_path
        ], check=True)

        # Convert raw to WAV for playback
        subprocess.run([
            "ffmpeg", "-y", "-f", "s16le", "-ar", bitrate, "-ac", "1",
            "-i", raw_path, output_wav_path
        ], check=True)

        return output_wav_path
    except Exception as e:
        return None


def get_audio_duration_seconds(path):

        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    path
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True
            )
            return int(float(result.stdout.strip()))
        except Exception as e:
            return 0


def save_and_decode_audio(fields, output_dir="../str/voicemails/received", output_path=None):

    try:
        if 7 not in fields:
            return None

        audio_field = fields[7]
        if not isinstance(audio_field, list) or len(audio_field) < 2:
            return None

        mode_code = audio_field[0]
        audio_data = audio_field[1]

        base_name = f"audio_{mode_code}_{int(time.time())}"
        if output_path:
            output_wav_path = output_path
            output_dir_final = os.path.dirname(output_path)
        else:
            output_dir_final = "../str/voicemails/received"
            output_wav_path = os.path.join(output_dir_final, f"{base_name}.wav")


        # Opus
        if mode_code == 16:
            # Opus decoding
            opus_path = os.path.join(output_dir_final, f"{base_name}.opus")
            with open(opus_path, "wb") as f:
                f.write(audio_data)

            subprocess.run([
                "ffmpeg", "-y", "-i", opus_path, output_wav_path
            ], check=True)
            os.remove(opus_path)

        else:
            # Assume Codec2
            codec2_path = os.path.join(output_dir_final, f"{base_name}.c2")
            with open(codec2_path, "wb") as f:
                f.write(audio_data)

            result = decode_codec2_to_wav(codec2_path, output_wav_path,
                                          bitrate={4: 1200, 9: 3200}.get(mode_code, 1200))
            # After decoding completes:
            os.chmod(output_wav_path, 0o660)

            os.remove(codec2_path)
            if not result:
                return None

        duration = get_audio_duration_seconds(output_wav_path)
        return output_wav_path, duration

    except Exception as e:
        return None, 0
