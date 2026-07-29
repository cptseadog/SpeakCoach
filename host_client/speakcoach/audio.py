"""Mic capture and playback.

Capture records 16 kHz mono (Whisper's native rate). Push-to-talk endpointing
comes from the start/stop trigger itself; Silero VAD is deliberately deferred —
it only becomes useful for trimming trailing silence / always-on modes.
sounddevice imports lazily so commands that never touch audio still work on
hosts without libportaudio2.
"""

import io
import queue
import re
import threading

SAMPLE_RATE = 16000

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")


class Recorder:
    """Start/stop microphone capture; returns WAV bytes."""

    def __init__(self) -> None:
        self._stream = None
        self._frames: queue.Queue = queue.Queue()

    def start(self) -> None:
        import sounddevice as sd

        self._frames = queue.Queue()

        def callback(indata, frame_count, time_info, status):
            self._frames.put(indata.copy())

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="int16", callback=callback
        )
        self._stream.start()

    def stop(self) -> bytes:
        import numpy as np
        import soundfile as sf

        self._stream.stop()
        self._stream.close()
        self._stream = None

        chunks = []
        while not self._frames.empty():
            chunks.append(self._frames.get())
        if not chunks:
            return b""
        audio = np.concatenate(chunks)

        buf = io.BytesIO()
        sf.write(buf, audio, SAMPLE_RATE, format="WAV", subtype="PCM_16")
        return buf.getvalue()


def record_seconds(seconds: float) -> bytes:
    """One-shot fixed-duration capture (useful for non-interactive testing)."""
    import time

    rec = Recorder()
    rec.start()
    time.sleep(seconds)
    return rec.stop()


def rms(wav: bytes) -> float:
    """Overall RMS level of WAV bytes (0..1). Whisper hallucinates phrases like
    'Thank you.' on silence, so callers gate on this before transcribing."""
    import numpy as np
    import soundfile as sf

    data, _ = sf.read(io.BytesIO(wav), dtype="float32")
    return float(np.sqrt((data**2).mean())) if len(data) else 0.0


def play(wav: bytes) -> None:
    """Play WAV bytes on the default output device, blocking until done."""
    import sounddevice as sd
    import soundfile as sf

    data, sample_rate = sf.read(io.BytesIO(wav), dtype="float32")
    sd.play(data, sample_rate)
    sd.wait()


def split_sentences(text: str, min_chars: int = 30) -> list[str]:
    """Split text into sentence-ish chunks for incremental TTS. Very short
    sentences merge into their neighbor — tiny chunks sound choppy and waste
    per-request overhead."""
    parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(text) if p.strip()]
    merged: list[str] = []
    for part in parts:
        if merged and len(merged[-1]) < min_chars:
            merged[-1] += " " + part
        else:
            merged.append(part)
    return merged or ([text.strip()] if text.strip() else [])


def play_pipelined(texts: list[str], synthesize) -> None:
    """Speak chunks in order, synthesizing ahead in a background thread, so
    audio starts after the FIRST chunk is ready instead of the whole text.
    `synthesize(text) -> wav bytes`."""
    buf: queue.Queue = queue.Queue(maxsize=2)  # bounded: at most 2 chunks ahead

    def producer() -> None:
        try:
            for text in texts:
                buf.put(("wav", synthesize(text)))
        except Exception as e:
            buf.put(("err", e))
            return
        buf.put(("end", None))

    threading.Thread(target=producer, daemon=True).start()
    while True:
        kind, item = buf.get()
        if kind == "end":
            return
        if kind == "err":
            raise RuntimeError(f"TTS failed mid-speech: {item}")
        play(item)
