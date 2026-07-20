# CPU-only image. M2 adds Kokoro-82M (which pulls in PyTorch).
# M8 GPU note: Kokoro's torch dependency on the RTX 5060 Ti (sm_120) requires a
# CUDA 12.8+ base image, cu128 (or newer) wheels, and torch >= 2.7 — older
# cu124/cu126 wheels crash with "no kernel image is available".
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

EXPOSE 8002
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8002"]
