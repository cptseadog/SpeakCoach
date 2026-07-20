"""ASR service — faster-whisper behind an OpenAI-compatible endpoint.

The model loads in a background thread at startup (first run downloads the
weights into the /models volume), so /health responds immediately;
model_loaded flips to true when loading finishes.
"""

import io
import os
import threading
import time

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse

DEVICE = os.environ.get("DEVICE", "cpu")
MODEL = os.environ.get("ASR_MODEL", "distil-large-v3")
# int8 on CPU, float16 on GPU — the standard fast configs for CTranslate2
COMPUTE_TYPE = "float16" if DEVICE == "cuda" else "int8"
CPU_THREADS = min(8, os.cpu_count() or 4)

app = FastAPI(title="speakcoach-asr")

_state = {"model": None, "loaded": False, "error": None}


def _load() -> None:
    try:
        from faster_whisper import WhisperModel

        _state["model"] = WhisperModel(
            MODEL,
            device=DEVICE,
            compute_type=COMPUTE_TYPE,
            cpu_threads=CPU_THREADS,
            download_root="/models/whisper",
        )
        _state["loaded"] = True
    except Exception as e:
        _state["error"] = f"{type(e).__name__}: {e}"


@app.on_event("startup")
def startup() -> None:
    threading.Thread(target=_load, daemon=True).start()


@app.get("/health")
def health():
    return {
        "status": "ok" if _state["error"] is None else "error",
        "service": "asr",
        "device": DEVICE,
        "model": MODEL,
        "compute_type": COMPUTE_TYPE,
        "model_loaded": _state["loaded"],
        "error": _state["error"],
    }


@app.post("/v1/audio/transcriptions")
def transcribe(
    file: UploadFile = File(...),
    model: str = Form(default=""),  # accepted for OpenAI compatibility, ignored
    language: str = Form(default="en"),
    response_format: str = Form(default="json"),
):
    if not _state["loaded"]:
        detail = _state["error"] or "model still loading, retry shortly"
        return JSONResponse(status_code=503, content={"error": detail})
    if response_format not in ("json", "text"):
        return JSONResponse(status_code=400, content={"error": "response_format must be json or text"})

    audio = io.BytesIO(file.file.read())
    start = time.monotonic()
    try:
        segments, info = _state["model"].transcribe(audio, language=language or None)
        text = " ".join(seg.text.strip() for seg in segments).strip()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"{type(e).__name__}: {e}"})
    elapsed = time.monotonic() - start

    if response_format == "text":
        return text
    return {
        "text": text,
        "language": info.language,
        "duration": round(info.duration, 2),
        "transcribe_seconds": round(elapsed, 2),
    }
