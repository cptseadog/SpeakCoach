"""TTS service — Kokoro-82M behind an OpenAI-compatible endpoint (Piper fallback).

Milestone 1: API skeleton only; the model is wired in Milestone 2.
"""

import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse

DEVICE = os.environ.get("DEVICE", "cpu")
VOICE = os.environ.get("TTS_VOICE", "af_heart")
BACKEND = os.environ.get("TTS_BACKEND", "kokoro")

app = FastAPI(title="speakcoach-tts")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "tts",
        "device": DEVICE,
        "backend": BACKEND,
        "voice": VOICE,
        "model_loaded": False,
    }


@app.post("/v1/audio/speech")
def speech():
    return JSONResponse(
        status_code=503,
        content={"error": "TTS model not loaded yet (arrives in Milestone 2)"},
    )
