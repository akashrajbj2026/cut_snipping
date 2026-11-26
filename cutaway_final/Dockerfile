FROM python:3.12-slim

# ffmpeg/ffprobe are required for cutting and stitching video
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Light dependency set for small hosts (no local whisper / opencv)
COPY backend/requirements-render.txt backend/requirements-render.txt
RUN pip install --no-cache-dir -r backend/requirements-render.txt

COPY backend backend
COPY frontend frontend

WORKDIR /app/backend

# Render provides the port in $PORT
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]
