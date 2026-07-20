"""Daily mini-lesson generation from recent frequent error patterns.

Idempotent per day: rerunning `speakcoach lesson` prints today's stored lesson
instead of regenerating, so the systemd timer and manual runs coexist.
"""

import json
from datetime import date

from .config import Config
from .db import get_lesson, insert_lesson, mistake_examples, mistake_stats
from .llm_client import LLMClient

MIN_MISTAKES = 3  # below this there is no meaningful pattern to teach
WINDOW_DAYS = 14
MAX_TOPICS = 2


def generate_daily_lesson(config: Config) -> None:
    today = date.today().isoformat()

    existing = get_lesson(config.db_path, today)
    if existing:
        topics, content = existing
        print(f"Today's lesson (already generated, topics: {', '.join(json.loads(topics))}):\n")
        print(content)
        return

    stats = mistake_stats(config.db_path, days=WINDOW_DAYS)
    total = sum(n for _, n in stats)
    if total < MIN_MISTAKES:
        print(
            f"Not enough logged mistakes to build a lesson ({total} in the last "
            f"{WINDOW_DAYS} days, need {MIN_MISTAKES}). Do a few practice rounds first."
        )
        return

    topics = [category for category, _ in stats[:MAX_TOPICS]]
    examples = mistake_examples(config.db_path, topics, days=WINDOW_DAYS)

    print(f"Generating today's lesson (topics: {', '.join(topics)})...")
    content = LLMClient(config).generate_lesson(topics, examples)

    insert_lesson(config.db_path, today, json.dumps(topics), content)
    print()
    print(content)
