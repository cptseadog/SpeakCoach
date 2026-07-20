# CPU-only image. faster-whisper runs on CTranslate2, so no PyTorch/CUDA is
# needed even for the GPU build — CTranslate2's CUDA support ships in the wheel.
# M3 adds faster-whisper here; M1 is the API skeleton only.
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

EXPOSE 8001
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
