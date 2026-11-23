import threading

import numpy as np

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
