import pytest

from infrastructure.door.geometry import cross, on_segment


def test_cross_detects_turn_direction():
    assert cross((0,0), (1,0), (0,1)) > 0
    assert cross((0,0), (1,0), (0,-1)) < 0
    assert cross((0,0), (1,0), (2,0)) == 0


@pytest.mark.parametrize('point,expected', [
    ((0,0), True),
    ((1,0), True),
    ((2,0), True),
    ((1,.5), False),
    ((3,0), False),
])
def test_on_segment(point, expected):
    assert on_segment((0,0), (2,0), point) == expected
