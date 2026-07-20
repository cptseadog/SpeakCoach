# CPU-only image. faster-whisper runs on CTranslate2, so no PyTorch is needed;
# CTranslate2's CUDA support is in the same wheel, making the M8 GPU flip a
# config change (DEVICE=cuda), not an image change — the GPU overlay just needs
# the NVIDIA runtime libraries visible (nvidia container toolkit provides them).
FROM python:3.12-slim

# Whisper weights land in the asr-models volume, not the image
ENV HF_HOME=/models/hf

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

EXPOSE 8001
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
