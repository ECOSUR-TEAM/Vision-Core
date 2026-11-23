from pathlib import Path

import pytest

from vision_core.core.config import (
    Settings,
    SettingsError,
    environment_with_relay_camera,
    redact_sensitive,
)
from vision_core.core.config.settings_helpers import valid_rtsp_url

MODEL = str(Path("yolov8n.pt").resolve())


def complete_env(**overrides):
    env = {
        "VISION_CORE_RTSP_URL": "rtsp://localhost:8554/entrada",
    }
    env.update(overrides)
    return env


def test_settings_defaults(monkeypatch):
    settings = Settings.from_env(
        complete_env(),
        validate_startup=True,
    )
    assert settings.video.open_timeout_ms == 5000
    assert settings.video.transport == "tcp"
    assert settings.detection.confidence == 0.5
    assert settings.reid.ttl_seconds == 0
    assert settings.monitor.port == 8080
    assert settings.zones.confirmation_frames == 3
    assert settings.camera_quality.enabled is True
    assert settings.camera_quality.sample_every_n_frames == 15
    assert settings.camera_quality.frozen_frames == 30
    assert settings.camera_quality.check_zones is True


def test_camera_quality_settings_overrides_and_camera_specific_precedence():
    settings = Settings.from_env(
        complete_env(
            VISION_CORE_CAMERA_ID="camera-1",
            VISION_CORE_CAMERA_QUALITY_MIN_BLUR_VARIANCE="120",
            VISION_CORE_CAMERA_QUALITY_CAMERA_1_MIN_BLUR_VARIANCE="75",
            VISION_CORE_CAMERA_QUALITY_CAMERA_1_CHECK_BLUR="0",
            VISION_CORE_CAMERA_QUALITY_CHECK_ZONES="0",
        )
    )
    assert settings.camera_quality.min_blur_variance == 75
    assert settings.camera_quality.check_blur is False
    assert settings.camera_quality.check_zones is False


def test_settings_overrides():
    settings = Settings.from_env(
        complete_env(
            VISION_CORE_RTSP_TRANSPORT="udp",
            VISION_CORE_RECONNECT_ATTEMPTS="9",
            VISION_CORE_REID_THRESHOLD="0.91",
            VISION_CORE_MONITOR_PORT="9090",
        )
    )
    assert settings.video.transport == "udp"
    assert settings.video.reconnect_attempts == 9
    assert settings.reid.threshold == 0.91
    assert settings.monitor.port == 9090


@pytest.mark.parametrize(
    "variable,value",
    [
        ("VISION_CORE_RTSP_URL", "http://localhost/entrada"),
        ("VISION_CORE_OPEN_TIMEOUT_MS", "-1"),
        ("VISION_CORE_RECONNECT_DELAY_SECONDS", "not-a-number"),
        ("VISION_CORE_DETECTION_CONFIDENCE", "2"),
        ("VISION_CORE_MONITOR_UNCALIBRATED", "quizas"),
        ("VISION_CORE_REID_THRESHOLD", "-0.1"),
        ("VISION_CORE_MONITOR_PORT", "70000"),
        ("VISION_CORE_MONITOR_HOST", ""),
        ("VISION_CORE_MONITOR_HOST", "bad host"),
        ("VISION_CORE_MODEL_PATH", "/missing/yolov8n.pt"),
        ("VISION_CORE_CAMERA_QUALITY_SAMPLE_EVERY_N_FRAMES", "0"),
        ("VISION_CORE_CAMERA_QUALITY_FROZEN_FRAMES", "1"),
        ("VISION_CORE_CAMERA_QUALITY_MIN_BLUR_VARIANCE", "-1"),
        ("VISION_CORE_CAMERA_QUALITY_MIN_BRIGHTNESS", "240"),
        ("VISION_CORE_CAMERA_QUALITY_MAX_BRIGHTNESS", "300"),
        ("VISION_CORE_CAMERA_QUALITY_MIN_BRIGHTNESS", "nan"),
        ("VISION_CORE_CAMERA_QUALITY_MAX_BRIGHTNESS", "inf"),
        ("VISION_CORE_CAMERA_QUALITY_CHECK_BLUR", "quizas"),
    ],
)
def test_settings_reports_invalid_values(variable, value):
    with pytest.raises(SettingsError) as exc:
        Settings.from_env(complete_env(**{variable: value}))
    message = str(exc.value)
    assert "Configuración inválida" in message
    assert variable in message


def test_settings_lists_missing_required_value():
    with pytest.raises(SettingsError) as exc:
        Settings.from_env({"VISION_CORE_MODEL_PATH": MODEL})
    assert "VISION_CORE_RTSP_URL" in str(exc.value)


def test_zones_path_is_validated_when_calibration_is_enabled(tmp_path):
    missing = tmp_path / "missing.json"
    with pytest.raises(SettingsError) as exc:
        Settings.from_env(
            complete_env(
                VISION_CORE_ZONES_FILE=str(missing),
                VISION_CORE_MONITOR_UNCALIBRATED="0",
                VISION_CORE_MONITOR_DEMO_ZONES="0",
            )
        )
    assert "VISION_CORE_ZONES_FILE" in str(exc.value)


def test_secret_redaction():
    assert redact_sensitive("rtsp://admin:password@camera.local/live") == "rtsp://admin:***@camera.local/live"


def test_validate_startup_false_skips_presence_checks():
    settings = Settings.from_env({}, validate_startup=False)
    assert settings.video.source == "rtsp"
    assert settings.video.rtsp_url is None
    assert settings.zones.uncalibrated is False


def test_monitor_uncalibrated_default_is_false():
    settings = Settings.from_env(complete_env(VISION_CORE_MONITOR_UNCALIBRATED="0"))
    assert settings.zones.uncalibrated is False


@pytest.mark.parametrize(
    "url",
    [
        "rtsp://host:notaport/entrada",
        "rtsp://host:99999/entrada",
        "rtsp://host con espacio/entrada",
        "http://host/entrada",
        "rtsp://host/entrada",
    ],
)
def test_valid_rtsp_url(url):
    expected = url.startswith("rtsp://") and " " not in url and "notaport" not in url and ":99999" not in url
    assert valid_rtsp_url(url) == expected


def test_redact_sensitive_password_only():
    assert redact_sensitive("rtsp://:secret@camera.local/live") == "rtsp://:***@camera.local/live"


def test_redact_sensitive_http_credentials():
    assert redact_sensitive("http://user:secret@host:8080/path") == "http://user:***@host:8080/path"


def test_redact_sensitive_invalid_port_redacts_anyway():
    assert redact_sensitive("rtsp://user:secret@host:notaport/live") == "rtsp://user:***@host/live"


def test_environment_with_relay_camera():
    env = environment_with_relay_camera("rtsp://relay:15554/live.sdp")
    assert env["FRIGATE_CAMERA_RTSP_URL"] == "rtsp://relay:15554/live.sdp"
    assert "PATH" in env
