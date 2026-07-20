"""SQLite access. Schema per the project brief; writes begin in Milestone 5."""

import sqlite3
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
