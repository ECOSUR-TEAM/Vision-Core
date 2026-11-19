FROM python:3.11-slim AS camera-bridge
WORKDIR /app
COPY src/vision_core/scripts/camera_bridge.py /app/camera_bridge.py
CMD ["python", "/app/camera_bridge.py", "serve"]

FROM python:3.11-slim AS runtime
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-cpu.txt ./
RUN pip install --no-cache-dir -r requirements-cpu.txt \
    && pip install --no-cache-dir -r requirements.txt
COPY src /app/src
COPY main.py /app/main.py
COPY config /app/config
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
ENV VISION_CORE_MONITOR_HOST=0.0.0.0
CMD ["python", "main.py", "--host", "0.0.0.0"]
