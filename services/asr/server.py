"""ASR service — faster-whisper behind an OpenAI-compatible endpoint.

Milestone 1: API skeleton only; the model is wired in Milestone 3.
"""

import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse

DEVICE = os.environ.get("DEVICE", "cpu")
MODEL = os.environ.get("ASR_MODEL", "distil-large-v3")

app = FastAPI(title="speakcoach-asr")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "asr",
        "device": DEVICE,
        "model": MODEL,
        "model_loaded": False,
    }


@app.post("/v1/audio/transcriptions")
def transcribe():
    return JSONResponse(
        status_code=503,
        content={"error": "ASR model not loaded yet (arrives in Milestone 3)"},
    )
