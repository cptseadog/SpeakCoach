"""Configuration loaded from the repo-root .env (falling back to .env.example)."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_env() -> None:
    for name in (".env", ".env.example"):
        path = REPO_ROOT / name
        if path.exists():
            load_dotenv(path)
            return


@dataclass
class Config:
    device: str = field(default_factory=lambda: os.environ.get("DEVICE", "cpu"))
    asr_model: str = field(default_factory=lambda: os.environ.get("ASR_MODEL", "distil-large-v3"))
    llm_model: str = field(default_factory=lambda: os.environ.get("LLM_MODEL", "qwen3:14b"))
    # hot path can use a smaller/faster model than coaching; defaults to LLM_MODEL
    dictation_model: str = field(default_factory=lambda: os.environ.get("DICTATION_MODEL") or os.environ.get("LLM_MODEL", "qwen3:14b"))
    tts_backend: str = field(default_factory=lambda: os.environ.get("TTS_BACKEND", "kokoro"))
    tts_voice: str = field(default_factory=lambda: os.environ.get("TTS_VOICE", "af_heart"))
    asr_url: str = field(default_factory=lambda: os.environ.get("ASR_URL", "http://127.0.0.1:8001"))
    tts_url: str = field(default_factory=lambda: os.environ.get("TTS_URL", "http://127.0.0.1:8002"))
    llm_url: str = field(default_factory=lambda: os.environ.get("LLM_URL", "http://127.0.0.1:11434"))
    injection_backend: str = field(default_factory=lambda: os.environ.get("INJECTION_BACKEND", "clipboard"))
    hotkey: str = field(default_factory=lambda: os.environ.get("HOTKEY", "ctrl+alt+space"))
    db_path: Path = field(default_factory=lambda: Path(os.environ.get("DB_PATH", "~/.local/share/speakcoach/speakcoach.db")).expanduser())
    audio_keep: bool = field(default_factory=lambda: os.environ.get("AUDIO_KEEP", "false").lower() == "true")


def load_config() -> Config:
    _load_env()
    return Config()
