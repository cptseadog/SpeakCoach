"""Pronunciation scoring extension point.

Deliberately a no-op in v1: ASR text is accent-robust and normalizes spelling,
so it masks mispronunciation. A v2 implementation would use a phoneme /
forced-alignment model against retained audio (see AUDIO_KEEP).
"""

from abc import ABC, abstractmethod
from pathlib import Path


class PronunciationScorer(ABC):
    @abstractmethod
    def score(self, audio_path: Path, transcript: str) -> dict | None:
        """Return pronunciation feedback, or None if unavailable."""


class NoOpPronunciationScorer(PronunciationScorer):
    def score(self, audio_path: Path, transcript: str) -> dict | None:
        return None
