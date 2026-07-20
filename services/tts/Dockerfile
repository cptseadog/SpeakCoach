# CPU image: torch comes from the CPU wheel index (small, no CUDA).
# M8 GPU note: on the RTX 5060 Ti (sm_120) swap the torch index for a CUDA
# 12.8+ base with cu128 wheels and torch >= 2.7 — older cu124/cu126 wheels
# crash with "no kernel image is available".
FROM python:3.12-slim

# espeak-ng: misaki's phonemization fallback for out-of-lexicon words
RUN apt-get update && apt-get install -y --no-install-recommends espeak-ng \
    && rm -rf /var/lib/apt/lists/*

# Kokoro weights (~330 MB) land in the tts-models volume, not the image
ENV HF_HOME=/models/hf

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY server.py .

EXPOSE 8002
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8002"]
