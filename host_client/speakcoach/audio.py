"""Mic capture, Silero VAD endpointing, and playback.

Playback lands here in Milestone 2; capture arrives in Milestone 3.
sounddevice imports lazily so commands that never touch audio still work on
hosts without libportaudio2.
"""

import io


def record_utterance() -> bytes:
    """Capture one push-to-talk utterance as WAV bytes."""
    raise NotImplementedError("audio capture arrives in Milestone 3")


def play(wav: bytes) -> None:
    """Play WAV bytes on the default output device, blocking until done."""
    import sounddevice as sd
    import soundfile as sf

    data, sample_rate = sf.read(io.BytesIO(wav), dtype="float32")
    sd.play(data, sample_rate)
    sd.wait()
