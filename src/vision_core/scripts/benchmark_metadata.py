"""Metadata compartida entre el generador sintético y el benchmark nocturno."""

import os
import platform
from importlib.metadata import PackageNotFoundError, version

GENERATOR_VERSION = "1.0.0"
VIDEO_SEED = 20261120


def package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "unknown"


def environment_metadata(*, device: str, detector: str) -> dict[str, str]:
    return {
        "generator_version": GENERATOR_VERSION,
        "device": device,
        "detector": detector,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "numpy": package_version("numpy"),
        "opencv": package_version("opencv-python"),
        "ultralytics": package_version("ultralytics"),
        "runner": os.getenv("GITHUB_RUNNER_NAME", "local"),
    }
