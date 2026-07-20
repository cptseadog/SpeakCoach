"""Thin HTTP client for the TTS service (OpenAI-compatible /v1/audio/speech)."""

import httpx

from .config import Config


class TTSClient:
    def __init__(self, config: Config):
        self.base_url = config.tts_url
        self.voice = config.tts_voice

    def synthesize(self, text: str, voice: str | None = None, speed: float = 1.0) -> bytes:
        """Return WAV bytes for `text`. Generous timeout — CPU synthesis is slow."""
        resp = httpx.post(
            f"{self.base_url}/v1/audio/speech",
            json={
                "input": text,
                "voice": voice or self.voice,
                "speed": speed,
                "response_format": "wav",
            },
            timeout=httpx.Timeout(120.0, connect=5.0),
        )
        if resp.status_code != 200:
            try:
                detail = resp.json().get("error", resp.text)
            except ValueError:
                detail = resp.text
            raise RuntimeError(f"TTS service error ({resp.status_code}): {detail}")
        return resp.content
