import numpy as np

from tests.fakes.fake_reid import FakeReID
from vision_core.features.reid.infrastructure.dependencies import build_reid


def test_build_reid_accepts_injected_memory_and_embedder():
    memory = FakeReID()

    def embedder(crop):
        return np.ones(4)

    dependencies = build_reid(memory=memory, embedder=embedder)

    assert dependencies.memory is memory
    assert dependencies.embedder is embedder
