from pathlib import Path

import numpy as np
import pytest

from vision_core.core.config import CameraQualitySettings
from vision_core.features.camera_health.application.camera_quality_monitor import CameraQualityMonitor
from vision_core.features.camera_health.domain import quality_reasons as reasons

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "camera_quality"


def fixture(name):
    return np.load(FIXTURES / f"{name}.npy")


def monitor(**overrides):
    return CameraQualityMonitor(CameraQualitySettings(sample_every_n_frames=1, frozen_frames=2, **overrides))


def test_good_frame_is_healthy():
    observation = monitor().observe(fixture("good"))

    assert observation is not None
    assert observation.status == reasons.STATUS_OK
    assert observation.reason is None
    assert not any(observation.signals.values())


def test_blurry_frame_is_detected():
    observation = monitor().observe(fixture("blurry"))

    assert observation.reason == reasons.BLURRY_FRAME
    assert observation.signals[reasons.BLURRY_FRAME] is True


def test_dark_frame_is_detected():
    observation = monitor().observe(fixture("dark"))

    assert observation.reason == reasons.EXPOSURE_OUT_OF_RANGE
    assert observation.signals[reasons.EXPOSURE_OUT_OF_RANGE] is True


def test_wrong_resolution_is_detected():
    detector = CameraQualityMonitor(
        CameraQualitySettings(sample_every_n_frames=1),
        expected_frame_size=(64, 48),
    )

    observation = detector.observe(fixture("wrong_resolution"))

    assert observation.reason == reasons.RESOLUTION_MISMATCH
    assert (observation.width, observation.height) == (48, 36)


def test_frozen_frames_are_detected_and_recover():
    detector = monitor()
    assert detector.observe(fixture("frozen_a")).reason is None
    assert detector.observe(fixture("frozen_b")).reason is None
    frozen = detector.observe(fixture("frozen_b"))

    assert frozen.reason == reasons.FROZEN_FRAME
    assert detector.observe(fixture("moving")).reason is None


def test_stale_zones_are_detected_without_schema_validation():
    from vision_core.features.door.infrastructure.config.zone_loader import load_zones

    zones = load_zones("config/zones.example.json")
    detector = CameraQualityMonitor(
        CameraQualitySettings(sample_every_n_frames=1),
        expected_frame_size=(64, 48),
        zones=zones,
    )

    observation = detector.observe(fixture("good"))

    assert observation.reason == reasons.ZONES_STALE
    assert observation.signals[reasons.ZONES_STALE] is True


@pytest.mark.parametrize(
    ("option", "image", "signal"),
    [
        ("check_blur", "blurry", reasons.BLURRY_FRAME),
        ("check_exposure", "dark", reasons.EXPOSURE_OUT_OF_RANGE),
        ("check_frozen", "frozen_b", reasons.FROZEN_FRAME),
    ],
)
def test_each_signal_can_be_disabled(option, image, signal):
    detector = monitor(**{option: False})
    detector.observe(fixture("frozen_a"))

    observation = detector.observe(fixture(image))

    assert observation is not None
    assert observation.signals[signal] is False


def test_monitor_can_be_disabled_entirely():
    detector = CameraQualityMonitor(CameraQualitySettings(enabled=False))

    assert detector.observe(fixture("blurry")) is None


def test_monitor_samples_only_every_n_frames():
    detector = CameraQualityMonitor(CameraQualitySettings(sample_every_n_frames=3))

    assert detector.observe(fixture("good")) is None
    assert detector.observe(fixture("good")) is None
    assert detector.observe(fixture("good")) is not None


def test_invalid_frame_does_not_raise_and_reports_error():
    errors = []
    detector = CameraQualityMonitor(CameraQualitySettings(sample_every_n_frames=1), on_error=errors.append)

    assert detector.observe(np.zeros((8, 8), dtype=np.uint8)) is None
    assert len(errors) == 1


def test_monitor_accepts_externally_sampled_frames():
    detector = CameraQualityMonitor(CameraQualitySettings(sample_every_n_frames=3))

    assert detector.observe(fixture("good"), sampled=True) is not None
