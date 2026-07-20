"""SpeakCoach CLI entry point."""

import argparse

from . import __version__
from .coaching import run_practice
from .config import load_config
from .dictation import run_dictation
from .lessons import generate_daily_lesson


def main() -> None:
    parser = argparse.ArgumentParser(prog="speakcoach", description="Local English dictation + coaching")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("dictate", help="push-to-talk dictation hot path (Milestone 4)")
    sub.add_parser("practice", help="coaching session with feedback (Milestone 6)")
    sub.add_parser("lesson", help="generate today's mini-lesson (Milestone 7)")

    args = parser.parse_args()
    config = load_config()
    {
        "dictate": run_dictation,
        "practice": run_practice,
        "lesson": generate_daily_lesson,
    }[args.command](config)


if __name__ == "__main__":
    main()
