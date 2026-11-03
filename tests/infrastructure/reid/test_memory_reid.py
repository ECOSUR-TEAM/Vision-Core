import numpy as np

from domain.entities import BBox
from infrastructure.reid import memory_reid
from infrastructure.reid.memory_reid import InMemoryReID


BBOX = BBox(0, 0, 10, 10)


def test_resolve_recovers_person_id_for_similar_embedding(monkeypatch):
    current_time = 1000.0
    monkeypatch.setattr(memory_reid.time, "time", lambda: current_time)

    reid = InMemoryReID()
    stored_embedding = np.array([1.0, 0.0])
    reid.mark_lost("person-1", stored_embedding)

    recovered_id = reid.resolve(2, np.array([0.99, 0.1]), BBOX)

    assert recovered_id == "person-1"


def test_resolve_creates_new_id_for_dissimilar_embedding(monkeypatch):
    current_time = 1000.0
    monkeypatch.setattr(memory_reid.time, "time", lambda: current_time)

    reid = InMemoryReID()
    reid.mark_lost("person-1", np.array([1.0, 0.0]))

    resolved_id = reid.resolve(2, np.array([0.0, 1.0]), BBOX)

    assert resolved_id != "person-1"
    assert resolved_id in reid._active.values()


def test_resolve_creates_new_id_for_expired_entry(monkeypatch):
    current_time = 1000.0
    monkeypatch.setattr(memory_reid.time, "time", lambda: current_time)

    reid = InMemoryReID()
    reid.mark_lost("person-1", np.array([1.0, 0.0]))

    current_time += memory_reid.TTL_SECONDS + 1
    resolved_id = reid.resolve(2, np.array([1.0, 0.0]), BBOX)

    assert resolved_id != "person-1"
    assert "person-1" not in reid._lost
