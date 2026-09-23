"""Opt-in integration test: local video/weights, real YOLO, no downloads or mocks."""

import os
from pathlib import Path

import cv2
import pytest

from domain.entities import Detection
from domain.ports import DetectorManager
from infrastructure.detection.benchmark import benchmark_video
from infrastructure.detection.yolo_detector_manager import YoloDetectorManager


def test_process_on_real_video():
    video = os.environ.get("DETECTION_TEST_VIDEO")
    model = os.environ.get("DETECTION_TEST_MODEL")
    if not video or not model:
        pytest.skip("Configura DETECTION_TEST_VIDEO y DETECTION_TEST_MODEL (ver README)")
    assert Path(video).is_file(), f"Video inexistente: {video}"
    assert Path(model).is_file(), f"Pesos inexistentes: {model}"

    detector = YoloDetectorManager(model)
    previous_ids = set()
    reused_ids = 0
    observed_detections = 0

    class CheckedDetector(DetectorManager):
        def process(self, frame):
            nonlocal previous_ids, reused_ids, observed_detections
            assert frame.ndim == 3 and frame.shape[2] == 3
            detections = detector.process(frame)
            assert isinstance(detections, list)
            ids = set()
            for detection in detections:
                assert isinstance(detection, Detection)
                assert detection.class_id == 0
                assert 0.5 < detection.confidence <= 1
                assert isinstance(detection.track_id, int) and detection.track_id > 0
                assert detection.track_id not in ids
                ids.add(detection.track_id)
                bbox = detection.bbox
                assert 0 <= bbox.x1 < bbox.x2 <= frame.shape[1]
                assert 0 <= bbox.y1 < bbox.y2 <= frame.shape[0]
            reused_ids += len(ids & previous_ids)
            observed_detections += len(detections)
            previous_ids = ids
            return detections

    report = benchmark_video(video, CheckedDetector(), seconds=30)
    assert report["video_seconds"] >= 30
    assert report["frames"] > 0
    assert observed_detections > 0, "El video debe contener personas detectables"
    assert reused_ids > 0, "No se conservaron IDs entre frames consecutivos"
    assert report["process_fps"] > 0
    # No hardware-dependent FPS threshold, nor a claim of perfect identity tracking.


def test_benchmark_rejects_short_video(tmp_path):
    import numpy as np

    path = tmp_path / "short.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (32, 32))
    assert writer.isOpened()
    try:
        writer.write(np.zeros((32, 32, 3), dtype=np.uint8))
    finally:
        writer.release()

    class EmptyDetector(DetectorManager):
        def process(self, frame):
            return []

    with pytest.raises(ValueError, match="Video insuficiente"):
        benchmark_video(str(path), EmptyDetector())
