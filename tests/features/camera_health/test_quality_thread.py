import threading

import numpy as np
import pytest

from vision_core.features.camera_health.application.quality_thread import QualityThread


def test_quality_thread_analyzes_sampled_frame_off_the_caller_thread():
    analyzed = []
    done = threading.Event()

    def analyze(frame):
        analyzed.append(frame)
        done.set()

    worker = QualityThread(analyze)
    worker.start()
    try:
        worker.submit(np.zeros((8, 8, 3), dtype=np.uint8))
        assert done.wait(2)
    finally:
        assert worker.close(timeout=2)

    assert len(analyzed) == 1
    assert analyzed[0].shape == (8, 8, 3)


def test_quality_thread_reports_analysis_errors_without_raising():
    errors = []
    worker = QualityThread(lambda _frame: 1 / 0, on_error=errors.append)
    worker.start()
    try:
        worker.submit(np.zeros((8, 8, 3), dtype=np.uint8))
        assert worker.failed.wait(2)
    finally:
        assert worker.close(timeout=2)

    assert isinstance(worker.error, ZeroDivisionError)
    assert len(errors) == 1


def test_quality_thread_rejects_invalid_sample_interval():
    with pytest.raises(ValueError, match="sample_every_n_frames"):
        QualityThread(lambda _frame: None, sample_every_n_frames=0)


def test_quality_thread_copies_only_sampled_frames():
    analyzed = []
    done = threading.Event()

    def analyze(frame):
        analyzed.append(frame)
        done.set()

    worker = QualityThread(analyze, sample_every_n_frames=3)
    worker.start()
    try:
        frame = np.zeros((8, 8, 3), dtype=np.uint8)
        worker.submit(frame)
        worker.submit(frame)
        assert not analyzed
        worker.submit(frame)
        assert done.wait(2)
    finally:
        assert worker.close(timeout=2)

    assert len(analyzed) == 1
    frame[:] = 255
    assert analyzed[0].mean() == 0
