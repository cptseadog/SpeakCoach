"""SQLite access. Schema per the project brief; writes begin in Milestone 5."""

import sqlite3
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS utterance (
  id INTEGER PRIMARY KEY,
  ts TEXT NOT NULL,
  mode TEXT NOT NULL,           -- 'dictation' | 'practice'
  raw_transcript TEXT NOT NULL, -- straight from ASR
  cleaned_text TEXT,            -- what was injected / the correction target
  audio_path TEXT               -- optional retained wav for future pronunciation v2
);
CREATE TABLE IF NOT EXISTS mistake (
  id INTEGER PRIMARY KEY,
  utterance_id INTEGER REFERENCES utterance(id),
  category TEXT NOT NULL,       -- article, tense, preposition, word_choice, agreement, fluency
  original TEXT NOT NULL,
  correction TEXT NOT NULL,
  explanation TEXT,
  severity INTEGER              -- 1..3
);
CREATE TABLE IF NOT EXISTS lesson (
  id INTEGER PRIMARY KEY,
  date TEXT NOT NULL,
  topics TEXT NOT NULL,         -- JSON: the 1-2 error patterns targeted
  content TEXT NOT NULL         -- generated mini-lesson + practice prompts
);
CREATE TABLE IF NOT EXISTS chat_session (
  id INTEGER PRIMARY KEY,
  started_ts TEXT NOT NULL,
  ended_ts TEXT,
  backend TEXT NOT NULL,        -- 'local' | 'api'
  model TEXT NOT NULL,
  correct_mode INTEGER NOT NULL DEFAULT 0,
  summary TEXT                  -- end-of-session note from the chat model
);
CREATE TABLE IF NOT EXISTS chat_message (
  id INTEGER PRIMARY KEY,
  session_id INTEGER REFERENCES chat_session(id),
  role TEXT NOT NULL,           -- 'user' | 'assistant'
  content TEXT NOT NULL,
  utterance_id INTEGER REFERENCES utterance(id)  -- user turns only
);
"""


def init_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def log_utterance(
    db_path: Path,
    mode: str,
    raw_transcript: str,
    cleaned_text: str | None,
    audio_path: str | None = None,
) -> int | None:
    """Persist one utterance. Never raises — the hot path must not break on
    logging problems; failures print a warning and return None."""
    ts = datetime.now().isoformat(timespec="seconds")
    try:
        conn = init_db(db_path)
        try:
            with conn:
                cur = conn.execute(
                    "INSERT INTO utterance (ts, mode, raw_transcript, cleaned_text, audio_path)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (ts, mode, raw_transcript, cleaned_text, audio_path),
                )
            return cur.lastrowid
        finally:
            conn.close()
    except (sqlite3.Error, OSError) as e:
        print(f"  (warning: failed to log utterance: {e})")
        return None


def update_utterance_cleaned(db_path: Path, utterance_id: int | None, cleaned: str) -> None:
    """Backfill cleaned_text once practice analysis produces the corrected form."""
    if utterance_id is None:
        return
    try:
        conn = init_db(db_path)
        try:
            with conn:
                conn.execute(
                    "UPDATE utterance SET cleaned_text = ? WHERE id = ?", (cleaned, utterance_id)
                )
        finally:
            conn.close()
    except (sqlite3.Error, OSError) as e:
        print(f"  (warning: failed to update utterance: {e})")


def insert_mistakes(db_path: Path, utterance_id: int | None, mistakes: list[dict]) -> int:
    """Persist coach-found mistakes; returns how many rows landed. Never raises."""
    if not mistakes:
        return 0
    try:
        conn = init_db(db_path)
        try:
            with conn:
                conn.executemany(
                    "INSERT INTO mistake (utterance_id, category, original, correction,"
                    " explanation, severity) VALUES (?, ?, ?, ?, ?, ?)",
                    [
                        (utterance_id, m["category"], m["original"], m["correction"],
                         m["explanation"], m["severity"])
                        for m in mistakes
                    ],
                )
            return len(mistakes)
        finally:
            conn.close()
    except (sqlite3.Error, KeyError, OSError) as e:
        print(f"  (warning: failed to log mistakes: {e})")
        return 0


def create_chat_session(db_path: Path, backend: str, model: str, correct_mode: bool) -> int | None:
    try:
        conn = init_db(db_path)
        try:
            with conn:
                cur = conn.execute(
                    "INSERT INTO chat_session (started_ts, backend, model, correct_mode)"
                    " VALUES (?, ?, ?, ?)",
                    (datetime.now().isoformat(timespec="seconds"), backend, model, int(correct_mode)),
                )
            return cur.lastrowid
        finally:
            conn.close()
    except (sqlite3.Error, OSError) as e:
        print(f"  (warning: failed to create chat session: {e})")
        return None


def end_chat_session(db_path: Path, session_id: int | None, summary: str | None) -> None:
    if session_id is None:
        return
    try:
        conn = init_db(db_path)
        try:
            with conn:
                conn.execute(
                    "UPDATE chat_session SET ended_ts = ?, summary = ? WHERE id = ?",
                    (datetime.now().isoformat(timespec="seconds"), summary, session_id),
                )
        finally:
            conn.close()
    except (sqlite3.Error, OSError) as e:
        print(f"  (warning: failed to close chat session: {e})")


def insert_chat_message(
    db_path: Path,
    session_id: int | None,
    role: str,
    content: str,
    utterance_id: int | None = None,
) -> None:
    if session_id is None:
        return
    try:
        conn = init_db(db_path)
        try:
            with conn:
                conn.execute(
                    "INSERT INTO chat_message (session_id, role, content, utterance_id)"
                    " VALUES (?, ?, ?, ?)",
                    (session_id, role, content, utterance_id),
                )
        finally:
            conn.close()
    except (sqlite3.Error, OSError) as e:
        print(f"  (warning: failed to log chat message: {e})")


def learner_profile(db_path: Path, days: int = 30) -> str:
    """Compact, deterministic description of the learner from collected data,
    for embedding in chat system prompts. No LLM call."""
    try:
        conn = init_db(db_path)
        try:
            since = (f"-{days} days",)
            n_utt = conn.execute(
                "SELECT COUNT(*) FROM utterance WHERE ts >= datetime('now', ?)", since
            ).fetchone()[0]
            cats = conn.execute(
                "SELECT m.category, COUNT(*) n FROM mistake m"
                " JOIN utterance u ON u.id = m.utterance_id"
                " WHERE u.ts >= datetime('now', ?)"
                " GROUP BY m.category ORDER BY n DESC LIMIT 4",
                since,
            ).fetchall()
            examples = conn.execute(
                "SELECT original, correction FROM mistake ORDER BY id DESC LIMIT 3"
            ).fetchall()
        finally:
            conn.close()
    except (sqlite3.Error, OSError):
        return "No learner data available yet; assume an intermediate learner."

    if n_utt < 5 and not cats:
        return (
            "The learner is new to this tool, so there is no reliable error data yet. "
            "Assume a motivated intermediate learner."
        )

    parts = [f"Over the last {days} days the learner produced {n_utt} logged utterances."]
    if cats:
        freq = ", ".join(f"{category} ({n}×)" for category, n in cats)
        parts.append(f"Most frequent error categories: {freq}.")
    if examples:
        ex = "; ".join(f'"{orig}" → "{corr}"' for orig, corr in examples)
        parts.append(f"Recent corrections: {ex}.")
    return " ".join(parts)


def mistake_stats(db_path: Path, days: int = 14) -> list[tuple[str, int]]:
    """(category, count) for mistakes in the last `days`, most frequent first."""
    conn = init_db(db_path)
    try:
        return conn.execute(
            "SELECT m.category, COUNT(*) AS n FROM mistake m"
            " JOIN utterance u ON u.id = m.utterance_id"
            " WHERE u.ts >= datetime('now', ?)"
            " GROUP BY m.category ORDER BY n DESC",
            (f"-{days} days",),
        ).fetchall()
    finally:
        conn.close()


def mistake_examples(db_path: Path, categories: list[str], days: int = 14, limit: int = 12) -> list[tuple]:
    """(category, original, correction, explanation) rows for the given categories."""
    conn = init_db(db_path)
    try:
        marks = ",".join("?" * len(categories))
        return conn.execute(
            f"SELECT m.category, m.original, m.correction, m.explanation FROM mistake m"
            f" JOIN utterance u ON u.id = m.utterance_id"
            f" WHERE u.ts >= datetime('now', ?) AND m.category IN ({marks})"
            f" ORDER BY m.id DESC LIMIT ?",
            (f"-{days} days", *categories, limit),
        ).fetchall()
    finally:
        conn.close()


def get_lesson(db_path: Path, date: str) -> tuple | None:
    conn = init_db(db_path)
    try:
        return conn.execute(
            "SELECT topics, content FROM lesson WHERE date = ? ORDER BY id DESC LIMIT 1",
            (date,),
        ).fetchone()
    finally:
        conn.close()


def insert_lesson(db_path: Path, date: str, topics: str, content: str) -> None:
    conn = init_db(db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO lesson (date, topics, content) VALUES (?, ?, ?)",
                (date, topics, content),
            )
    finally:
        conn.close()


def recent_utterances(db_path: Path, limit: int = 10) -> list[tuple]:
    conn = init_db(db_path)
    try:
        return conn.execute(
            "SELECT id, ts, mode, raw_transcript, cleaned_text FROM utterance"
            " ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
