"""Mic capture and playback.

Capture records 16 kHz mono (Whisper's native rate). Push-to-talk endpointing
comes from the start/stop trigger itself; Silero VAD is deliberately deferred —
it only becomes useful for trimming trailing silence / always-on modes.
sounddevice imports lazily so commands that never touch audio still work on
hosts without libportaudio2.
"""

import io
import queue

SAMPLE_RATE = 16000


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


def play(wav: bytes) -> None:
    """Play WAV bytes on the default output device, blocking until done."""
    import sounddevice as sd
    import soundfile as sf

    data, sample_rate = sf.read(io.BytesIO(wav), dtype="float32")
    sd.play(data, sample_rate)
    sd.wait()
