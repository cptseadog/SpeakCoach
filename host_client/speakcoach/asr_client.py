"""Thin HTTP client for the ASR service (OpenAI-compatible /v1/audio/transcriptions)."""

import httpx

from . import http
from .config import Config


class ASRClient:
    def __init__(self, config: Config):
        self.base_url = config.asr_url

    def transcribe(self, wav: bytes) -> dict:
        """Return the service's JSON: text, language, duration, transcribe_seconds."""
        resp = http.post(
            "ASR",
            f"{self.base_url}/v1/audio/transcriptions",
            files={"file": ("utterance.wav", wav, "audio/wav")},
            data={"language": "en"},
            timeout=httpx.Timeout(120.0, connect=5.0),
        )
        if resp.status_code != 200:
            try:
                detail = resp.json().get("error", resp.text)
            except ValueError:
                detail = resp.text
            raise RuntimeError(f"ASR service error ({resp.status_code}): {detail}")
        return resp.json()
