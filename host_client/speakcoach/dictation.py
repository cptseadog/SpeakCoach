"""Job A hot path: capture -> ASR -> light clean -> inject.

Must stay fast: no TTS, no mistake analysis; logging (M5) will hang off the
end without blocking. Two triggers toggle recording:
  - Enter in the terminal
  - SIGUSR1, so a GNOME custom shortcut can trigger it globally:
      sh -c 'kill -USR1 $(cat $XDG_RUNTIME_DIR/speakcoach-dictate.pid)'
Desktop notifications (best-effort notify-send) give feedback when the
terminal isn't visible.
"""

import os
import queue
import signal
import subprocess
import threading
import time
from pathlib import Path

from .asr_client import ASRClient
from .audio import Recorder, rms
from .config import Config
from .db import log_utterance
from .inject import get_backend
from .llm_client import LLMClient

SILENCE_RMS = 0.001  # measured ambient on this setup is ~0.0001; speech is >0.01


def _notify(summary: str, body: str = "") -> None:
    try:
        subprocess.run(
            ["notify-send", "-a", "SpeakCoach", "-t", "3000", summary, body],
            timeout=2, capture_output=True,
        )
    except Exception:
        pass  # notifications are cosmetic


def _pidfile() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    return Path(runtime) / "speakcoach-dictate.pid"


def send_toggle() -> None:
    """Signal a running dictation loop to start/stop recording (hotkey helper)."""
    pidfile = _pidfile()
    try:
        os.kill(int(pidfile.read_text().strip()), signal.SIGUSR1)
    except (FileNotFoundError, ValueError, ProcessLookupError):
        raise SystemExit("no running `speakcoach dictate` found")


def run_dictation(config: Config) -> None:
    asr = ASRClient(config)
    llm = LLMClient(config)
    backend = get_backend(config)

    events: queue.Queue = queue.Queue()
    signal.signal(signal.SIGUSR1, lambda *_: events.put("toggle"))

    def stdin_reader() -> None:
        while True:
            try:
                input()
            except EOFError:
                return
            events.put("toggle")

    threading.Thread(target=stdin_reader, daemon=True).start()

    pidfile = _pidfile()
    pidfile.write_text(str(os.getpid()))
    print(f"SpeakCoach dictation (model: {llm.dictation_model}, inject: {config.injection_backend})")
    print("Toggle recording with Enter here, or bind a GNOME shortcut to:")
    print(f"  sh -c 'kill -USR1 $(cat {pidfile})'")
    print("Ctrl+C to quit.\n[ready]")

    recorder = Recorder()
    recording = False
    try:
        while True:
            try:
                events.get()
            except KeyboardInterrupt:
                break
            if not recording:
                recorder.start()
                recording = True
                print("[recording] toggle again to stop...")
                _notify("🎙️ Recording…")
                continue

            recording = False
            wav = recorder.stop()
            if len(wav) < 1000 or rms(wav) < SILENCE_RMS:
                print("[ready] (no speech captured)")
                _notify("SpeakCoach", "heard nothing")
                continue

            t0 = time.monotonic()
            raw = asr.transcribe(wav)["text"]
            t1 = time.monotonic()
            if not raw:
                print("[ready] (silence)")
                _notify("SpeakCoach", "heard nothing")
                continue
            cleaned = llm.clean_dictation(raw)
            t2 = time.monotonic()
            note = backend.inject(cleaned)

            # text is already delivered; logging happens off the critical path
            audio_path = None
            if config.audio_keep:
                audio_dir = config.db_path.parent / "audio"
                audio_dir.mkdir(parents=True, exist_ok=True)
                audio_path = str(audio_dir / (time.strftime("%Y%m%d-%H%M%S") + ".wav"))
                Path(audio_path).write_bytes(wav)
            log_utterance(config.db_path, "dictation", raw, cleaned, audio_path)

            print(f"  raw:     {raw}")
            print(f"  cleaned: {cleaned}")
            print(f"  [asr {t1 - t0:.1f}s | clean {t2 - t1:.1f}s] {note}")
            print("[ready]")
            _notify("📋 " + note, cleaned[:120])
    finally:
        pidfile.unlink(missing_ok=True)
    print("\nbye")
