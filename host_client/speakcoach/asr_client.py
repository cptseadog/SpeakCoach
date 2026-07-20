"""Thin HTTP client for the ASR service (OpenAI-compatible /v1/audio/transcriptions)."""

from .config import Config


class ASRClient:
    def __init__(self, config: Config):
        self.base_url = config.asr_url

    def transcribe(self, wav: bytes) -> str:
        raise NotImplementedError("implemented in Milestone 3")
