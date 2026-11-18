import numpy as np
import pytest

from vision_core.features.video.application.mappers.video_mapper import (
    dto_to_frame,
    frame_to_dto,
    validate_frame,
)

FRAME = np.zeros((3, 5, 3), dtype=np.uint8)
FRAME[:, :, 0] = 10
FRAME[:, :, 1] = 20
FRAME[:, :, 2] = 30


def test_roundtrip_preserves_bgr_frame():
    response = frame_to_dto(FRAME)

    assert response.format == "png"
    assert response.width == 5
    assert response.height == 3
    assert np.array_equal(dto_to_frame(response), FRAME)


def test_none_frame_roundtrip():
    response = frame_to_dto(None)

    assert response.frame_png is None
    assert dto_to_frame(response) is None


@pytest.mark.parametrize(
    "frame",
    [
        None,
        np.zeros((2, 2)),
        np.zeros((2, 2, 4), dtype=np.uint8),
        np.zeros((0, 2, 3), dtype=np.uint8),
        FRAME.astype(float),
    ],
)
def test_invalid_frames_rejected(frame):
    with pytest.raises(ValueError):
        validate_frame(frame)


def test_expected_size_checked_by_mapper():
    with pytest.raises(ValueError):
        validate_frame(FRAME, (100, 100))
