import numpy as np
import pytest

from infrastructure.detection.iou import iou


@pytest.mark.parametrize("first,second,expected", [
    ([0, 0, 10, 10], [0, 0, 10, 10], 1.0),
    ([0, 0, 10, 10], [10, 0, 20, 10], 0.0),
    ([0, 0, 10, 10], [5, 0, 15, 10], 1 / 3),
    ([0, 0, 10, 10], [2, 2, 8, 8], 0.36),
    ([0, 0, 0, 0], [0, 0, 0, 0], 0.0),
])
def test_iou_geometry(first, second, expected):
    assert iou(np.array(first), np.array(second)) == pytest.approx(expected)
    assert iou(np.array(second), np.array(first)) == pytest.approx(expected)
