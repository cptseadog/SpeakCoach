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
