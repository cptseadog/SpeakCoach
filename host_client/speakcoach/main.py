"""SpeakCoach CLI entry point."""

import argparse

from . import __version__
from .audio import play
from .coaching import run_practice
from .config import load_config
from .dictation import run_dictation
from .lessons import generate_daily_lesson
from .tts_client import TTSClient


def main() -> None:
    parser = argparse.ArgumentParser(prog="speakcoach", description="Local English dictation + coaching")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("dictate", help="push-to-talk dictation hot path (Milestone 4)")
    sub.add_parser("practice", help="coaching session with feedback (Milestone 6)")
    sub.add_parser("lesson", help="generate today's mini-lesson (Milestone 7)")
    p_speak = sub.add_parser("speak", help="synthesize a sentence via the TTS service and play it")
    p_speak.add_argument("text", help="text to speak")
    p_speak.add_argument("--voice", help="Kokoro voice (default: TTS_VOICE from .env)")
    p_speak.add_argument("--speed", type=float, default=1.0)
    p_speak.add_argument("--out", help="also save the WAV to this path")

    args = parser.parse_args()
    config = load_config()

    if args.command == "speak":
        wav = TTSClient(config).synthesize(args.text, voice=args.voice, speed=args.speed)
        if args.out:
            with open(args.out, "wb") as f:
                f.write(wav)
            print(f"saved {len(wav)} bytes to {args.out}")
        play(wav)
        return

    {
        "dictate": run_dictation,
        "practice": run_practice,
        "lesson": generate_daily_lesson,
    }[args.command](config)


if __name__ == "__main__":
    main()
