import sys

import pytest

from vision_core.core.domain.bbox import BBox
from vision_core.features.detection.domain.entities.detection import Detection
from vision_core.features.door.infrastructure.config.zone_loader import load_zones
from vision_core.features.video.infrastructure.adapters.file_video_source import FileVideoSource
from vision_core.scripts.create_pipeline_sample import main as create_pipeline_sample

FRAME_COUNT = 35
EXPECTED_EVENTS = (
    ("PERSON_ENTERED", "exterior", "interior"),
    ("PERSON_EXITED", "interior", "exterior"),
    ("FALSE_ALARM", "exterior", "fuera"),
    ("PERSON_ENTERED", "exterior", "interior"),
    ("PERSON_EXITED", "interior", "exterior"),
)


def pytest_collection_modifyitems(items):
    for item in items:
        path = str(item.fspath).replace("\\", "/")
        if "/tests/e2e/" in path:
            item.add_marker(pytest.mark.e2e)
            item.add_marker(pytest.mark.slow)
        elif "/tests/integration/" in path:
            item.add_marker(pytest.mark.integration)
        elif "/tests/performance/" in path:
            item.add_marker(pytest.mark.performance)


def _detection(x, track_id=1):
    return Detection(
        bbox=BBox(x - 10, 100, x + 10, 140),
        class_id=0,
        confidence=0.9,
        track_id=track_id,
    )


def pytest_addoption(parser):
    parser.addoption(
        "--regen-golden",
        action="store_true",
        default=False,
        help="Regenerate deterministic replay golden files (requires explicit approval).",
    )


@pytest.fixture
def regen_golden(request):
    return request.config.getoption("--regen-golden")


@pytest.fixture(scope="session")
def synthetic_sample(tmp_path_factory):
    folder = tmp_path_factory.mktemp("synthetic_video") / "demo"
    original_argv = sys.argv
    sys.argv = ["create_pipeline_sample", str(folder)]
    try:
        create_pipeline_sample()
    finally:
        sys.argv = original_argv
    return folder


@pytest.fixture(scope="session")
def synthetic_zones(synthetic_sample):
    return load_zones(synthetic_sample / "zones.json")


@pytest.fixture
def synthetic_video(synthetic_sample):
    return FileVideoSource(synthetic_sample / "sample.avi")


@pytest.fixture
def synthetic_scene():
    positions = (
        [100] * 2
        + [250] * 2
        + [260] * 2
        + [100] * 2
        + [110] * 2
        + [-5] * 2
        + [100] * 2
        + [250] * 2
        + [None] * 4
        + [250] * 2
        + [260] * 2
        + [100] * 11
    )
    assert len(positions) == FRAME_COUNT
    detections = []
    lost_ids = []
    for index, x in enumerate(positions):
        track_id = 1 if index < 16 else 2
        detections.append([] if x is None else [_detection(x, track_id)])
        lost_ids.append([1] if index == 16 else [])
    return detections, lost_ids, EXPECTED_EVENTS
