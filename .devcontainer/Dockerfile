FROM mcr.microsoft.com/devcontainers/python:1-3.11-bullseye

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 make \
    && rm -rf /var/lib/apt/lists/*
