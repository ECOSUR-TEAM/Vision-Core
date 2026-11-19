import os
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Mapping

from .settings_camera import CameraSettings
from .settings_detection import DetectionSettings
from .settings_error import SettingsError
from .settings_helpers import valid_rtsp_url
from .settings_logging import LoggingSettings
from .settings_monitor import MonitorSettings
from .settings_performance import PerformanceSettings
from .settings_reid import ReIDSettings
from .settings_video import VideoSettings
from .settings_zones import ZonesSettings


@dataclass(frozen=True, slots=True)
class Settings:
    video: VideoSettings
    detection: DetectionSettings
    reid: ReIDSettings
    zones: ZonesSettings
    monitor: MonitorSettings
    logging: LoggingSettings
    performance: PerformanceSettings
    camera: CameraSettings

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None, *, validate_startup: bool = True) -> "Settings":
        env = os.environ if environ is None else environ
        errors: list[str] = []

        def integer(name: str, default: int) -> int:
            raw = env.get(name)
            if raw is None or raw.strip() == "":
                return default
            try:
                return int(raw)
            except (TypeError, ValueError):
                errors.append(f"{name}: debe ser un entero")
                return default

        def floating(name: str, default: float) -> float:
            raw = env.get(name)
            if raw is None or raw.strip() == "":
                return default
            try:
                return float(raw)
            except (TypeError, ValueError):
                errors.append(f"{name}: debe ser un número")
                return default

        def boolean(name: str, default: bool = False) -> bool:
            raw = env.get(name)
            if raw is None or raw.strip() == "":
                return default
            value = raw.strip().lower()
            if value in {"1", "true", "yes", "on"}:
                return True
            if value in {"0", "false", "no", "off"}:
                return False
            errors.append(f"{name}: debe ser 1/0, true/false, yes/no u on/off")
            return default

        source = env.get("VISION_CORE_VIDEO_SOURCE", "rtsp").strip().lower()
        rtsp_url = env.get("VISION_CORE_RTSP_URL", "").strip() or None
        video_path_raw = env.get("VISION_CORE_VIDEO_PATH", "").strip()
        video_path = Path(video_path_raw).expanduser() if video_path_raw else None
        transport = env.get("VISION_CORE_RTSP_TRANSPORT", "tcp").strip().lower()
        open_timeout = integer("VISION_CORE_OPEN_TIMEOUT_MS", 5000)
        read_timeout = integer("VISION_CORE_READ_TIMEOUT_MS", 5000)
        reconnect_attempts = integer("VISION_CORE_RECONNECT_ATTEMPTS", 5)
        reconnect_delay = floating("VISION_CORE_RECONNECT_DELAY_SECONDS", 2.0)
        decoder_threads = integer("VISION_CORE_DECODER_THREADS", 1)
        ffmpeg_options = env.get("OPENCV_FFMPEG_CAPTURE_OPTIONS", "").strip() or None

        if source not in {"rtsp", "file"}:
            errors.append("VISION_CORE_VIDEO_SOURCE: debe ser rtsp o file")
        if source == "rtsp":
            if rtsp_url is None and validate_startup:
                errors.append("VISION_CORE_RTSP_URL: variable obligatoria para source=rtsp")
            elif rtsp_url is not None and validate_startup and not valid_rtsp_url(rtsp_url):
                errors.append("VISION_CORE_RTSP_URL: debe ser una URL rtsp:// o rtsps:// válida")
        elif validate_startup:
            if video_path is None:
                errors.append("VISION_CORE_VIDEO_PATH: variable obligatoria para source=file")
            elif not video_path.is_file():
                errors.append(f"VISION_CORE_VIDEO_PATH: el archivo no existe: {video_path}")
        if transport not in {"tcp", "udp"}:
            errors.append("VISION_CORE_RTSP_TRANSPORT: debe ser tcp o udp")
        if open_timeout <= 0:
            errors.append("VISION_CORE_OPEN_TIMEOUT_MS: debe ser mayor que 0")
        if read_timeout <= 0:
            errors.append("VISION_CORE_READ_TIMEOUT_MS: debe ser mayor que 0")
        if reconnect_attempts < 0:
            errors.append("VISION_CORE_RECONNECT_ATTEMPTS: debe ser mayor o igual que 0")
        if not isfinite(reconnect_delay) or reconnect_delay < 0:
            errors.append("VISION_CORE_RECONNECT_DELAY_SECONDS: debe ser finito y no negativo")
        if decoder_threads < 0:
            errors.append("VISION_CORE_DECODER_THREADS: debe ser mayor o igual que 0")

        configured_model_path = env.get("VISION_CORE_MODEL_PATH")
        model_path = Path(configured_model_path or "yolov8n.pt").expanduser()
        detection_device = env.get("VISION_CORE_DETECTION_DEVICE", "").strip() or None
        confidence = floating("VISION_CORE_DETECTION_CONFIDENCE", 0.5)
        classes_raw = env.get("VISION_CORE_DETECTION_CLASSES", "0").strip()
        classes: tuple[int, ...] = ()
        if classes_raw:
            try:
                classes = tuple(int(item.strip()) for item in classes_raw.split(",") if item.strip())
            except ValueError:
                errors.append("VISION_CORE_DETECTION_CLASSES: use enteros separados por comas")
        tracking = boolean("VISION_CORE_TRACKING_ENABLED", True)
        max_missed = integer("VISION_CORE_TRACK_MAX_MISSED_FRAMES", 30)
        if configured_model_path and validate_startup and not model_path.is_file():
            errors.append(f"VISION_CORE_MODEL_PATH: el archivo no existe: {model_path}")
        if (
            detection_device is not None
            and detection_device not in {"cpu", "cuda"}
            and not detection_device.startswith("cuda:")
        ):
            errors.append("VISION_CORE_DETECTION_DEVICE: use cpu, cuda o cuda:<indice>")
        if not isfinite(confidence) or not 0 < confidence <= 1:
            errors.append("VISION_CORE_DETECTION_CONFIDENCE: debe estar entre 0 y 1")
        if not classes or any(item < 0 for item in classes):
            errors.append("VISION_CORE_DETECTION_CLASSES: debe contener clases no negativas")
        if max_missed < 1:
            errors.append("VISION_CORE_TRACK_MAX_MISSED_FRAMES: debe ser mayor que 0")

        reid_model = env.get("VISION_CORE_EMBEDDING_MODEL", "mobilenet_v3_small").strip()
        reid_device = env.get("VISION_CORE_EMBEDDING_DEVICE", "").strip() or None
        reid_threshold = floating("VISION_CORE_REID_THRESHOLD", 0.85)
        ambiguity_margin = floating("VISION_CORE_REID_AMBIGUITY_MARGIN", 0.03)
        reid_ttl = floating("VISION_CORE_REID_TTL_SECONDS", 0.0)
        gallery_size = integer("VISION_CORE_REID_GALLERY_SIZE", 8)
        if reid_model not in {"mobilenet_v3_small", "resnet50"}:
            errors.append("VISION_CORE_EMBEDDING_MODEL: use mobilenet_v3_small o resnet50")
        if reid_device is not None and reid_device not in {"cpu", "cuda"} and not reid_device.startswith("cuda:"):
            errors.append("VISION_CORE_EMBEDDING_DEVICE: use cpu, cuda o cuda:<indice>")
        if not isfinite(reid_threshold) or not 0 < reid_threshold <= 1:
            errors.append("VISION_CORE_REID_THRESHOLD: debe estar entre 0 y 1")
        if not isfinite(ambiguity_margin) or not 0 <= ambiguity_margin <= 1:
            errors.append("VISION_CORE_REID_AMBIGUITY_MARGIN: debe estar entre 0 y 1")
        if not isfinite(reid_ttl) or reid_ttl < 0:
            errors.append("VISION_CORE_REID_TTL_SECONDS: debe ser finito y no negativo")
        if gallery_size < 1:
            errors.append("VISION_CORE_REID_GALLERY_SIZE: debe ser mayor que 0")

        zones_raw = env.get("VISION_CORE_ZONES_FILE", "").strip()
        zones_file = Path(zones_raw).expanduser() if zones_raw else None
        confirmation_frames = integer("VISION_CORE_ZONE_CONFIRMATION_FRAMES", 3)
        demo_zones = boolean("VISION_CORE_MONITOR_DEMO_ZONES", False)
        uncalibrated = boolean("VISION_CORE_MONITOR_UNCALIBRATED", False)
        zones_missing = (
            zones_file is not None
            and validate_startup
            and not uncalibrated
            and not demo_zones
            and not zones_file.is_file()
        )
        if zones_missing:
            errors.append(f"VISION_CORE_ZONES_FILE: el archivo no existe: {zones_file}")
        if confirmation_frames < 1:
            errors.append("VISION_CORE_ZONE_CONFIRMATION_FRAMES: debe ser mayor que 0")

        monitor_host = env.get("VISION_CORE_MONITOR_HOST", "127.0.0.1").strip()
        monitor_port = integer("VISION_CORE_MONITOR_PORT", 8080)
        exit_on_error = boolean("VISION_CORE_MONITOR_EXIT_ON_ERROR", False)
        if not monitor_host:
            errors.append("VISION_CORE_MONITOR_HOST: no puede estar vacío")
        if not 1 <= monitor_port <= 65535:
            errors.append("VISION_CORE_MONITOR_PORT: debe estar entre 1 y 65535")

        log_level = env.get("VISION_CORE_LOG_LEVEL", "INFO").strip().upper()
        if log_level not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            errors.append("VISION_CORE_LOG_LEVEL: use CRITICAL, ERROR, WARNING, INFO o DEBUG")
        performance_interval = floating("VISION_CORE_PERFORMANCE_INTERVAL_SECONDS", 1.0)
        if not isfinite(performance_interval) or performance_interval <= 0:
            errors.append("VISION_CORE_PERFORMANCE_INTERVAL_SECONDS: debe ser mayor que 0")

        camera_url = env.get("FRIGATE_CAMERA_RTSP_URL", "").strip() or None
        if camera_url is not None and not valid_rtsp_url(camera_url):
            errors.append("FRIGATE_CAMERA_RTSP_URL: debe ser una URL rtsp:// o rtsps:// válida")

        if errors:
            raise SettingsError("Configuración inválida:\n- " + "\n- ".join(errors))

        return cls(
            video=VideoSettings(
                source,
                rtsp_url,
                video_path,
                transport,
                open_timeout,
                read_timeout,
                reconnect_attempts,
                reconnect_delay,
                decoder_threads,
                ffmpeg_options,
            ),
            detection=DetectionSettings(model_path, detection_device, confidence, classes, tracking, max_missed),
            reid=ReIDSettings(reid_model, reid_device, reid_threshold, ambiguity_margin, reid_ttl, gallery_size),
            zones=ZonesSettings(zones_file, confirmation_frames, demo_zones, uncalibrated),
            monitor=MonitorSettings(monitor_host, monitor_port, exit_on_error),
            logging=LoggingSettings(log_level),
            performance=PerformanceSettings(performance_interval),
            camera=CameraSettings(camera_url),
        )
