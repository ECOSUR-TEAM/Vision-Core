import numpy as np
import pytest

from tests.fakes.fake_reid import FakeReID
from vision_core.infrastructure.reid.memory_reid import InMemoryReID
from vision_core.shared.domain.bbox import BBox
from vision_core.shared.errors import ReIDError, codes

EMBEDDING = np.array([1.0, 0.0], dtype=np.float32)


def _assert_reid_contract(memory):
    for method in ("begin_frame", "resolve", "mark_lost"):
        assert callable(getattr(memory, method))
    memory.begin_frame({1})
    person_id = memory.resolve(1, EMBEDDING, BBox(0, 0, 10, 10))
    assert isinstance(person_id, str) and person_id
    assert memory.mark_lost(person_id, EMBEDDING) is None


def test_fake_reid_honours_port_contract():
    _assert_reid_contract(FakeReID())


def test_real_reid_honours_port_contract():
    _assert_reid_contract(InMemoryReID())


def test_real_reid_rejects_invalid_embedding_with_stable_code():
    with pytest.raises(ReIDError) as error:
        InMemoryReID().resolve(1, np.zeros(2, dtype=np.float32), BBox(0, 0, 10, 10))
    assert error.value.code == codes.REID_INPUT_INVALID
