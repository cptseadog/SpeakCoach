# Works on CPU and GPU (sm_120 verified). faster-whisper runs on CTranslate2 —
# no PyTorch. For GPU, the NVIDIA container toolkit injects the driver, but
# cuBLAS/cuDNN must come from the image: the pip wheels below provide them
# (adds ~1 GB; harmless when running on CPU).
FROM python:3.12-slim

ENV HF_HOME=/models/hf
# CTranslate2 dlopens these at runtime when DEVICE=cuda
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.12/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.12/site-packages/nvidia/cudnn/lib

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir nvidia-cublas-cu12 "nvidia-cudnn-cu12>=9"

COPY server.py .

EXPOSE 8001
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
