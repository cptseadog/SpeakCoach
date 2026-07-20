"""SpeakCoach CLI entry point."""

import argparse

from . import __version__
from .asr_client import ASRClient
from .audio import Recorder, play, record_seconds
from .coaching import run_practice
from .config import load_config
from .dictation import run_dictation
from .lessons import generate_daily_lesson
from .tts_client import TTSClient


def run_transcribe(config, seconds: float | None) -> None:
    """Milestone 3 loop: capture speech, print the raw ASR transcript."""
    asr = ASRClient(config)

    def transcribe_and_print(wav: bytes) -> None:
        if len(wav) < 1000:
            print("(no audio captured)")
            return
        result = asr.transcribe(wav)
        print(f"[{result['duration']}s audio, transcribed in {result['transcribe_seconds']}s]")
        print(result["text"] or "(silence)")

    if seconds:
        print(f"recording {seconds}s — speak now...")
        transcribe_and_print(record_seconds(seconds))
        return

    print("Press Enter to start recording, Enter again to stop. Ctrl+C to quit.")
    while True:
        try:
            input("\n[ready] Enter to record > ")
            rec = Recorder()
            rec.start()
            input("[recording] Enter to stop > ")
            transcribe_and_print(rec.stop())
        except (KeyboardInterrupt, EOFError):
            print("\nbye")
            return


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
    p_tr = sub.add_parser("transcribe", help="record from the mic and print the raw transcript")
    p_tr.add_argument("--seconds", type=float, help="record for a fixed duration instead of Enter-to-stop")
    sub.add_parser("toggle", help="toggle recording in a running `speakcoach dictate` (for hotkey bindings)")
    p_log = sub.add_parser("log", help="show recent logged utterances")
    p_log.add_argument("--limit", type=int, default=10)

    args = parser.parse_args()
    config = load_config()

    if args.command == "log":
        from .db import recent_utterances
        rows = recent_utterances(config.db_path, args.limit)
        if not rows:
            print(f"no utterances logged yet ({config.db_path})")
        for id_, ts, mode, raw, cleaned in rows:
            print(f"#{id_} [{ts}] ({mode})")
            print(f"  raw:     {raw}")
            print(f"  cleaned: {cleaned}")
        return

    if args.command == "toggle":
        from .dictation import send_toggle
        send_toggle()
        return

    if args.command == "transcribe":
        run_transcribe(config, args.seconds)
        return

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
