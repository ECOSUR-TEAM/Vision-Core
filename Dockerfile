FROM python:3.11-slim AS camera-bridge
WORKDIR /app
COPY scripts/camera_bridge.py /app/camera_bridge.py
CMD ["python", "/app/camera_bridge.py", "serve"]

FROM python:3.11-slim AS runtime
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
# CPU deployment: avoid pulling CUDA libraries for the laptop test stack.
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "infrastructure.monitor", "--host", "0.0.0.0"]
