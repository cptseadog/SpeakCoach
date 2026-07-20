"""Job A hot path: capture -> ASR -> light clean -> inject.

Must stay fast: no TTS, no mistake analysis, logging deferred off the critical path.
"""

from .config import Config


def run_dictation(config: Config) -> None:
    raise NotImplementedError("dictation hot path arrives in Milestone 4")
