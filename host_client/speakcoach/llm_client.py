"""Thin HTTP client for the LLM service (Ollama, OpenAI-compatible /v1)."""

from .config import Config


class LLMClient:
    def __init__(self, config: Config):
        self.base_url = config.llm_url
        self.model = config.llm_model

    def clean_dictation(self, raw_transcript: str) -> str:
        """Hot path: minimal fixes + punctuation, preserving meaning and voice."""
        raise NotImplementedError("implemented in Milestone 4")

    def analyze_mistakes(self, raw_transcript: str) -> list[dict]:
        """Cold path: structured mistakes (category/original/correction/explanation/
        severity) plus a native-idiomatic alternative. JSON-only, parsed defensively."""
        raise NotImplementedError("implemented in Milestone 6")
