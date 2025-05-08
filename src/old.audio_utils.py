"""
ffmpeg -i test_audio.wav -f s16le -ar 8000 -ac 1 input.raw
c2enc 1200 input.raw output.c2

c2dec 1200 output.c2 decoded.raw
ffmpeg -f s16le -ar 8000 -ac 1 -i decoded.raw decoded.wav

"""


import os
import subprocess
import logging
import time
from LXMF import LXMessage

# Output directory for audio files
AUDIO_OUT_DIR = "audio_out"
os.makedirs(AUDIO_OUT_DIR, exist_ok=True)

def encode_audio_to_codec2(input_path, output_path, bitrate=1200):
    """
    Converts an input WAV/MP3 file to raw, then encodes it to Codec2 using c2enc.
    """
    try:
        raw_path = output_path.replace(".c2", ".raw")
        # Convert input file to 8kHz, mono, 16-bit PCM raw format
        subprocess.run([
            "ffmpeg", "-y", "-i", input_path,
            "-f", "s16le", "-ar", "8000", "-ac", "1", raw_path
        ], check=True)

        # Encode raw audio to Codec2
        subprocess.run([
            "c2enc", str(bitrate), raw_path, output_path
        ], check=True)

        logging.info(f"[ENCODE] Encoded {input_path} → {output_path} using Codec2 @ {bitrate}bps")
        return output_path
    except Exception as e:
        logging.error(f"[ENCODE] Failed to encode audio: {e}")
        return None

def decode_codec2_to_wav(input_path, output_wav_path, bitrate=1200):
    """
    Decodes Codec2 audio back to WAV using c2dec + ffmpeg.
    """
    try:
        raw_path = input_path.replace(".c2", "_decoded.raw")

        # Decode .c2 to raw
        subprocess.run([
            "c2dec", str(bitrate), input_path, raw_path
        ], check=True)

        # Convert raw to WAV for playback
        subprocess.run([
            "ffmpeg", "-y", "-f", "s16le", "-ar", "8000", "-ac", "1",
            "-i", raw_path, output_wav_path
        ], check=True)

        logging.info(f"[DECODE] Decoded {input_path} → {output_wav_path}")
        return output_wav_path
    except Exception as e:
        logging.error(f"[DECODE] Failed to decode audio: {e}")
        return None

def save_and_decode_audio(fields, output_dir=AUDIO_OUT_DIR, output_path=None):
    """
    Extracts Codec2 or Opus payload from LXMF fields and decodes it to a WAV file.
    Returns (wav_path, duration_secs) or (None, 0) if decoding failed.
    """
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
            logging.warning(f"[DURATION] Failed to get duration: {e}")
            return 0

    try:
        if 7 not in fields:
            logging.warning("[AUDIO] No audio field (7) found in LXMF message.")
            return None, 0

        audio_field = fields[7]
        if not isinstance(audio_field, list) or len(audio_field) < 2:
            logging.warning("[AUDIO] Malformed audio field structure.")
            return None, 0

        mode_code = audio_field[0]
        audio_data = audio_field[1]

        base_name = f"audio_{mode_code}_{int(time.time())}"
        if output_path:
            output_wav_path = output_path
            output_dir_final = os.path.dirname(output_path)
        else:
            output_dir_final = output_dir or AUDIO_OUT_DIR
            output_wav_path = os.path.join(output_dir_final, f"{base_name}.wav")



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
                return None, 0

        duration = get_audio_duration_seconds(output_wav_path)
        logging.info(f"[DECODE] Decoded to {output_wav_path}, duration={duration}s")
        return output_wav_path, duration

    except Exception as e:
        logging.error(f"[AUDIO] Failed to decode audio field: {e}")
        return None, 0



def convert_audio_to_bytes(input_wav, codec="codec2", bitrate=1200):
    """
    Converts an input WAV file to encoded audio bytes for either Codec2 or Opus.
    Returns (mode_code, audio_bytes).
    """
    try:
        if codec == "codec2":
            raw_path = input_wav.replace(".wav", ".raw")
            c2_path = input_wav.replace(".wav", f"_{bitrate}.bin")

            subprocess.run([
                "ffmpeg", "-y", "-i", input_wav,
                "-f", "s16le", "-ar", "8000", "-ac", "1", raw_path
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
        logging.error(f"[ENCODE] Failed to encode {codec} audio: {e}")
        return None, None

def create_lxmf_audio_message(destination, source, input_wav, codec="codec2", title="Voice Message", bitrate=1200):
    """
    Creates an LXMF message with audio payload from WAV, using Codec2 or Opus.
    """
    try:
        mode_code, audio_bytes = convert_audio_to_bytes(input_wav, codec, bitrate)
        if not audio_bytes:
            raise Exception("No audio data encoded")

        lxm = LXMessage(
            destination,
            source,
            "Audio message attached",
            title,
            desired_method=LXMessage.DIRECT,
            include_ticket=True
        )
        lxm.fields[7] = [mode_code, audio_bytes]
        logging.info(f"[LXMF] Created LXMF message with {codec.upper()} audio (mode {mode_code})")
        return lxm
    except Exception as e:
        logging.error(f"[LXMF] Failed to create LXMF message: {e}")
        return None
