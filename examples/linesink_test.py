#!/usr/bin/env python3

import argparse
import sys
import time
import RNS
import LXST

def main():
    RNS.loglevel = RNS.LOG_INFO  # Set to RNS.LOG_DEBUG for more output

    parser = argparse.ArgumentParser(
        description="Test audio input/output pipeline with LXST codecs"
    )
    parser.add_argument(
        "codec", choices=["raw", "codec2", "opus"],
        help="Codec to use for the test pipeline"
    )
    parser.add_argument(
        "--source", choices=["mic", "file"], default="mic",
        help="Choose audio source: 'mic' for live input, 'file' for looped audio file"
    )
    parser.add_argument(
        "--file", type=str, default="./docs/speech_stereo.opus",
        help="Path to audio file (used if --source file is selected)"
    )
    parser.add_argument(
        "--frame_ms", type=int, default=40,
        help="Target frame size in milliseconds (default: 40)"
    )
    args = parser.parse_args()

    print(f"[INFO] Selected codec   : {args.codec}")
    print(f"[INFO] Selected source  : {args.source}")
    print(f"[INFO] Target frame size: {args.frame_ms} ms")

    if args.source == "file":
        if not os.path.exists(args.file):
            print(f"[ERROR] Audio file not found: {args.file}")
            sys.exit(1)
        selected_source = LXST.Sources.OpusFileSource(
            args.file, loop=True, target_frame_ms=args.frame_ms
        )
    else:
        selected_source = LXST.Sources.LineSource(target_frame_ms=args.frame_ms)

    loopback = LXST.Sources.Loopback()
    line_sink = LXST.Sinks.LineSink()

    # Codec and pipeline setup
    if args.codec == "raw":
        codec = LXST.Codecs.Raw()
    elif args.codec == "codec2":
        codec = LXST.Codecs.Codec2(mode=LXST.Codecs.Codec2.CODEC2_1600)
    elif args.codec == "opus":
        codec = LXST.Codecs.Opus(profile=LXST.Codecs.Opus.PROFILE_VOICE_LOW)
    else:
        print("[ERROR] Invalid codec selected.")
        sys.exit(1)

    # Set up encode → loopback → decode → speaker
    try:
        input_pipeline = LXST.Pipeline(source=selected_source, codec=codec, sink=loopback)
        output_pipeline = LXST.Pipeline(source=loopback, codec=codec, sink=line_sink)

        print("\n[INFO] Starting pipeline... Press ENTER to stop.\n")
        input_pipeline.start()
        output_pipeline.start()

        input()  # Wait for user to press ENTER

    finally:
        input_pipeline.stop()
        output_pipeline.stop()
        time.sleep(1)
        print("[INFO] Pipeline stopped. Exiting.")

if __name__ == "__main__":
    import os   
    main()
