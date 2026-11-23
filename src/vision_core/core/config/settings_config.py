import os
import re
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Mapping

from .settings_camera import CameraSettings
from .settings_camera_quality import CameraQualitySettings
from .settings_detection import DetectionSettings
from .settings_error import SettingsError
from .settings_helpers import normalize_monitor_host, parse_bool, valid_rtsp_url
from .settings_logging import LoggingSettings
from .settings_model_registry import DEFAULT_MODEL_REGISTRY_FILE, ModelRegistrySettings
from .settings_monitor import MonitorSettings
from .settings_performance import PerformanceSettings
from .settings_precision import is_supported_precision
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
    camera_quality: CameraQualitySettings
    models: ModelRegistrySettings

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
            parsed = parse_bool(name, env.get(name), default)
            if parsed is None:
                errors.append(f"{name}: debe ser 1/0, true/false, yes/no u on/off")
                return default
            return parsed

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
        detection_precision = env.get("VISION_CORE_DETECTION_PRECISION", "fp32").strip().lower()
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
        if not is_supported_precision(detection_precision):
            errors.append("VISION_CORE_DETECTION_PRECISION: use fp32, fp16 o int8")
        if detection_precision == "fp16" and (detection_device is None or detection_device == "cpu"):
            errors.append(
                "VISION_CORE_DETECTION_PRECISION: fp16 requiere VISION_CORE_DETECTION_DEVICE=cuda o cuda:<indice>"
            )
        if not isfinite(confidence) or not 0 < confidence <= 1:
            errors.append("VISION_CORE_DETECTION_CONFIDENCE: debe estar entre 0 y 1")
        if not classes or any(item < 0 for item in classes):
            errors.append("VISION_CORE_DETECTION_CLASSES: debe contener clases no negativas")
        if max_missed < 1:
            errors.append("VISION_CORE_TRACK_MAX_MISSED_FRAMES: debe ser mayor que 0")

        reid_model = env.get("VISION_CORE_EMBEDDING_MODEL", "mobilenet_v3_small").strip()
        reid_weights = env.get("VISION_CORE_EMBEDDING_WEIGHTS", "DEFAULT").strip().upper()
        reid_device = env.get("VISION_CORE_EMBEDDING_DEVICE", "").strip() or None
        reid_precision = env.get("VISION_CORE_EMBEDDING_PRECISION", "fp32").strip().lower()
        reid_threshold = floating("VISION_CORE_REID_THRESHOLD", 0.85)
        ambiguity_margin = floating("VISION_CORE_REID_AMBIGUITY_MARGIN", 0.03)
        reid_ttl = floating("VISION_CORE_REID_TTL_SECONDS", 0.0)
        gallery_size = integer("VISION_CORE_REID_GALLERY_SIZE", 8)
        if reid_model not in {
            "mobilenet_v3_small",
            "mobilenet_v3_small-int8",
            "mobilenet_v3_small-fp16",
            "resnet50",
        }:
            errors.append(
                "VISION_CORE_EMBEDDING_MODEL: use mobilenet_v3_small, "
                "mobilenet_v3_small-int8, mobilenet_v3_small-fp16 o resnet50"
            )
        if not is_supported_precision(reid_precision):
            errors.append("VISION_CORE_EMBEDDING_PRECISION: use fp32, fp16 o int8")
        if reid_precision == "fp16" and (reid_device is None or reid_device == "cpu"):
            errors.append(
                "VISION_CORE_EMBEDDING_PRECISION: fp16 requiere VISION_CORE_EMBEDDING_DEVICE=cuda o cuda:<indice>"
            )
        if reid_weights != "DEFAULT":
            errors.append("VISION_CORE_EMBEDDING_WEIGHTS: use DEFAULT")
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
        editor_enabled = boolean("VISION_CORE_ZONE_EDITOR_ENABLED", False)
        editor_token = env.get("VISION_CORE_ZONE_EDITOR_TOKEN", "").strip() or None
        editor_audit_raw = env.get("VISION_CORE_ZONE_EDITOR_AUDIT_FILE", "").strip()
        editor_audit_file = Path(editor_audit_raw).expanduser() if editor_audit_raw else None
        if editor_enabled and editor_token is None:
            errors.append("VISION_CORE_ZONE_EDITOR_TOKEN: obligatorio al habilitar el editor de zonas")
        if editor_enabled and editor_audit_file is None:
            errors.append("VISION_CORE_ZONE_EDITOR_AUDIT_FILE: obligatorio al habilitar el editor de zonas")
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

        monitor_host_raw = env.get("VISION_CORE_MONITOR_HOST", "127.0.0.1").strip()
        monitor_host = monitor_host_raw or "127.0.0.1"
        if not monitor_host_raw:
            errors.append("VISION_CORE_MONITOR_HOST: no puede estar vacío")
        else:
            try:
                monitor_host = normalize_monitor_host(monitor_host_raw)
            except ValueError:
                errors.append("VISION_CORE_MONITOR_HOST: debe ser una IP o un hostname válido")
                monitor_host = "127.0.0.1"
        monitor_port = integer("VISION_CORE_MONITOR_PORT", 8080)
        exit_on_error = boolean("VISION_CORE_MONITOR_EXIT_ON_ERROR", False)
        disk_check_path = env.get("VISION_CORE_DISK_CHECK_PATH", ".").strip() or "."
        if not 1 <= monitor_port <= 65535:
            errors.append("VISION_CORE_MONITOR_PORT: debe estar entre 1 y 65535")

        log_level = env.get("VISION_CORE_LOG_LEVEL", "INFO").strip().upper()
        log_json = boolean("VISION_CORE_LOG_JSON", True)
        camera_id = env.get("VISION_CORE_CAMERA_ID", "default").strip() or "default"
        if log_level not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            errors.append("VISION_CORE_LOG_LEVEL: use CRITICAL, ERROR, WARNING, INFO o DEBUG")
        if not camera_id or camera_id.lower() in {"none", "null"}:
            errors.append("VISION_CORE_CAMERA_ID: no puede estar vacío")

        safe_camera_id = re.sub(r"[^A-Za-z0-9]+", "_", camera_id).upper().strip("_") or "DEFAULT"
        quality_prefix = f"VISION_CORE_CAMERA_QUALITY_{safe_camera_id}_"

        def quality_name(suffix: str) -> str:
            specific = f"{quality_prefix}{suffix}"
            return specific if specific in env else f"VISION_CORE_CAMERA_QUALITY_{suffix}"

        quality_enabled = boolean(quality_name("ENABLED"), True)
        quality_sample_frames = integer(quality_name("SAMPLE_EVERY_N_FRAMES"), 15)
        quality_frozen_frames = integer(quality_name("FROZEN_FRAMES"), 30)
        quality_frozen_difference = floating(quality_name("FROZEN_DIFFERENCE"), 1.0)
        quality_min_blur = floating(quality_name("MIN_BLUR_VARIANCE"), 50.0)
        quality_min_brightness = floating(quality_name("MIN_BRIGHTNESS"), 25.0)
        quality_max_brightness = floating(quality_name("MAX_BRIGHTNESS"), 230.0)
        quality_check_resolution = boolean(quality_name("CHECK_RESOLUTION"), True)
        quality_check_frozen = boolean(quality_name("CHECK_FROZEN"), True)
        quality_check_blur = boolean(quality_name("CHECK_BLUR"), True)
        quality_check_exposure = boolean(quality_name("CHECK_EXPOSURE"), True)
        quality_check_zones = boolean(quality_name("CHECK_ZONES"), True)
        if quality_sample_frames < 1:
            errors.append(f"{quality_name('SAMPLE_EVERY_N_FRAMES')}: debe ser mayor que 0")
        if quality_frozen_frames < 2:
            errors.append(f"{quality_name('FROZEN_FRAMES')}: debe ser mayor o igual que 2")
        if not isfinite(quality_frozen_difference) or quality_frozen_difference < 0:
            errors.append(f"{quality_name('FROZEN_DIFFERENCE')}: debe ser finito y no negativo")
        if not isfinite(quality_min_blur) or quality_min_blur < 0:
            errors.append(f"{quality_name('MIN_BLUR_VARIANCE')}: debe ser finito y no negativo")
        if not isfinite(quality_min_brightness):
            errors.append(f"{quality_name('MIN_BRIGHTNESS')}: debe ser finito")
        if not isfinite(quality_max_brightness):
            errors.append(f"{quality_name('MAX_BRIGHTNESS')}: debe ser finito")
        elif isfinite(quality_min_brightness) and not 0 <= quality_min_brightness < quality_max_brightness <= 255:
            errors.append(
                f"{quality_name('MIN_BRIGHTNESS')} / {quality_name('MAX_BRIGHTNESS')}: requiere 0 <= min < max <= 255"
            )

        minimum_free_disk_mb = integer("VISION_CORE_MINIMUM_FREE_DISK_MB", 500)
        if minimum_free_disk_mb < 0:
            errors.append("VISION_CORE_MINIMUM_FREE_DISK_MB: debe ser mayor o igual que 0")
        performance_interval = floating("VISION_CORE_PERFORMANCE_INTERVAL_SECONDS", 1.0)
        if not isfinite(performance_interval) or performance_interval <= 0:
            errors.append("VISION_CORE_PERFORMANCE_INTERVAL_SECONDS: debe ser mayor que 0")

        camera_url = env.get("FRIGATE_CAMERA_RTSP_URL", "").strip() or None
        if camera_url is not None and not valid_rtsp_url(camera_url):
            errors.append("FRIGATE_CAMERA_RTSP_URL: debe ser una URL rtsp:// o rtsps:// válida")

        registry_raw = env.get("VISION_CORE_MODEL_REGISTRY_FILE", "").strip()
        registry_file = Path(registry_raw).expanduser() if registry_raw else DEFAULT_MODEL_REGISTRY_FILE
        detection_model_id = env.get("VISION_CORE_DETECTION_MODEL_ID", "detection.person.yolov8n").strip()
        embedding_model_id = env.get("VISION_CORE_EMBEDDING_MODEL_ID", "embedding.person.mobilenet_v3_small").strip()
        verify_checksums = boolean("VISION_CORE_MODEL_CHECKSUM_VERIFY", True)
        if validate_startup and not registry_file.is_file():
            errors.append(f"VISION_CORE_MODEL_REGISTRY_FILE: el archivo no existe: {registry_file}")
        if not detection_model_id:
            errors.append("VISION_CORE_DETECTION_MODEL_ID: no puede estar vacío")
        if not embedding_model_id:
            errors.append("VISION_CORE_EMBEDDING_MODEL_ID: no puede estar vacío")

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
            detection=DetectionSettings(
                model_path,
                detection_device,
                detection_precision,
                confidence,
                classes,
                tracking,
                max_missed,
            ),
            reid=ReIDSettings(
                reid_model,
                reid_weights,
                reid_device,
                reid_precision,
                reid_threshold,
                ambiguity_margin,
                reid_ttl,
                gallery_size,
            ),
            zones=ZonesSettings(
                zones_file,
                confirmation_frames,
                demo_zones,
                uncalibrated,
                editor_enabled,
                editor_token,
                editor_audit_file,
            ),
            monitor=MonitorSettings(monitor_host, monitor_port, exit_on_error, minimum_free_disk_mb, disk_check_path),
            logging=LoggingSettings(log_level, log_json, camera_id),
            performance=PerformanceSettings(performance_interval),
            camera=CameraSettings(camera_url),
            camera_quality=CameraQualitySettings(
                enabled=quality_enabled,
                sample_every_n_frames=quality_sample_frames,
                frozen_frames=quality_frozen_frames,
                frozen_difference=quality_frozen_difference,
                min_blur_variance=quality_min_blur,
                min_brightness=quality_min_brightness,
                max_brightness=quality_max_brightness,
                check_resolution=quality_check_resolution,
                check_frozen=quality_check_frozen,
                check_blur=quality_check_blur,
                check_exposure=quality_check_exposure,
                check_zones=quality_check_zones,
            ),
            models=ModelRegistrySettings(
                registry_file,
                detection_model_id,
                embedding_model_id,
                verify_checksums,
            ),
        )
