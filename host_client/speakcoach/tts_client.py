"""Thin HTTP client for the TTS service (OpenAI-compatible /v1/audio/speech)."""

from .config import Config


class TTSClient:
    def __init__(self, config: Config):
        self.base_url = config.tts_url
        self.voice = config.tts_voice

    def synthesize(self, text: str) -> bytes:
        raise NotImplementedError("implemented in Milestone 2")
