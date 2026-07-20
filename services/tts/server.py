"""TTS service — Kokoro-82M behind an OpenAI-compatible /v1/audio/speech.

The pipeline warms up in a background thread at startup (first run downloads
~330 MB of weights into the /models volume), so /health responds immediately;
model_loaded flips to true when warmup finishes.
"""

import io
import os
import threading

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

DEVICE = os.environ.get("DEVICE", "cpu")
DEFAULT_VOICE = os.environ.get("TTS_VOICE", "af_heart")
BACKEND = os.environ.get("TTS_BACKEND", "kokoro")
SAMPLE_RATE = 24000  # Kokoro output rate

app = FastAPI(title="speakcoach-tts")

_pipelines: dict = {}
_pipelines_lock = threading.Lock()
_state = {"loaded": False, "error": None}


def _lang_code(voice: str) -> str:
    # Kokoro voices encode language in the first letter: a=US, b=UK English
    return voice[0] if voice else "a"


def _get_pipeline(lang_code: str):
    from kokoro import KPipeline

    with _pipelines_lock:
        if lang_code not in _pipelines:
            _pipelines[lang_code] = KPipeline(lang_code=lang_code, device=DEVICE)
        return _pipelines[lang_code]


def _warmup() -> None:
    try:
        pipeline = _get_pipeline(_lang_code(DEFAULT_VOICE))
        list(pipeline("Warm up.", voice=DEFAULT_VOICE))
        _state["loaded"] = True
    except Exception as e:  # surfaced via /health rather than crashing the server
        _state["error"] = f"{type(e).__name__}: {e}"


@app.on_event("startup")
def startup() -> None:
    threading.Thread(target=_warmup, daemon=True).start()


@app.get("/health")
def health():
    return {
        "status": "ok" if _state["error"] is None else "error",
        "service": "tts",
        "device": DEVICE,
        "backend": BACKEND,
        "voice": DEFAULT_VOICE,
        "model_loaded": _state["loaded"],
        "error": _state["error"],
    }


class SpeechRequest(BaseModel):
    input: str
    voice: str | None = None
    model: str | None = None  # accepted for OpenAI compatibility, ignored
    response_format: str = "wav"
    speed: float = 1.0


@app.post("/v1/audio/speech")
def speech(req: SpeechRequest):
    import numpy as np
    import soundfile as sf

    if req.response_format != "wav":
        return JSONResponse(status_code=400, content={"error": "only response_format=wav is supported"})
    if not req.input.strip():
        return JSONResponse(status_code=400, content={"error": "input is empty"})
    if not _state["loaded"]:
        detail = _state["error"] or "model still warming up, retry shortly"
        return JSONResponse(status_code=503, content={"error": detail})

    voice = req.voice or DEFAULT_VOICE
    try:
        pipeline = _get_pipeline(_lang_code(voice))
        chunks = [audio for _, _, audio in pipeline(req.input, voice=voice, speed=req.speed)]
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"{type(e).__name__}: {e}"})
    if not chunks:
        return JSONResponse(status_code=400, content={"error": "no audio produced for input"})

    audio = np.concatenate([c.numpy() if hasattr(c, "numpy") else np.asarray(c) for c in chunks])
    buf = io.BytesIO()
    sf.write(buf, audio, SAMPLE_RATE, format="WAV")
    return Response(content=buf.getvalue(), media_type="audio/wav")
