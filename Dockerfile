FROM python:3.11-slim AS base
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --no-cache-dir --upgrade \
    pip==26.2.0 \
    setuptools==84.1.0 \
    wheel==0.46.2 \
    jaraco.context==6.1.0 \
    certifi==2026.10.18 \
    msgpack==1.2.3 \
    urllib3==2.8.0

FROM base AS camera-bridge
RUN python -m pip uninstall -y pip
WORKDIR /app
COPY src/vision_core/scripts/camera_bridge.py /app/camera_bridge.py
CMD ["python", "/app/camera_bridge.py", "serve"]

FROM base AS runtime
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-cpu.txt ./
RUN python -m pip install --no-cache-dir -r requirements-cpu.txt \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip uninstall -y pip
COPY src /app/src
COPY main.py /app/main.py
COPY config /app/config
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
ENV VISION_CORE_MONITOR_HOST=0.0.0.0
CMD ["python", "main.py", "--host", "0.0.0.0"]
