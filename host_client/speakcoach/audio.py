"""Mic capture, Silero VAD endpointing, and playback. Implemented in Milestone 3."""


def record_utterance() -> bytes:
    """Capture one push-to-talk utterance as WAV bytes."""
    raise NotImplementedError("audio capture arrives in Milestone 3")


def play(wav: bytes) -> None:
    """Play WAV audio on the default output device."""
    raise NotImplementedError("audio playback arrives in Milestone 2/6")
