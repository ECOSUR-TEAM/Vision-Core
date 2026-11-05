import numpy as np

from domain.entities import BBox
from infrastructure.reid import memory_reid
from infrastructure.reid.memory_reid import InMemoryReID


BBOX = BBox(0, 0, 10, 10)


def test_resolve_recovers_person_id_for_similar_embedding(monkeypatch):
    current_time = 1000.0
    monkeypatch.setattr(memory_reid.time, "monotonic", lambda: current_time)

    reid = InMemoryReID()
    stored_embedding = np.array([1.0, 0.0])
    reid.mark_lost("person-1", stored_embedding)

    recovered_id = reid.resolve(2, np.array([0.99, 0.1]), BBOX)

    assert recovered_id == "person-1"


def test_resolve_creates_new_id_for_dissimilar_embedding(monkeypatch):
    current_time = 1000.0
    monkeypatch.setattr(memory_reid.time, "monotonic", lambda: current_time)

    reid = InMemoryReID()
    reid.mark_lost("person-1", np.array([1.0, 0.0]))

    resolved_id = reid.resolve(2, np.array([0.0, 1.0]), BBOX)

    assert resolved_id != "person-1"
    assert resolved_id in reid._active.values()


def test_resolve_creates_new_id_for_expired_entry(monkeypatch):
    current_time = 1000.0
    monkeypatch.setattr(memory_reid.time, "monotonic", lambda: current_time)

    reid = InMemoryReID()
    reid.mark_lost("person-1", np.array([1.0, 0.0]))

    current_time += memory_reid.TTL_SECONDS + 1
    resolved_id = reid.resolve(2, np.array([1.0, 0.0]), BBOX)

    assert resolved_id != "person-1"
    assert "person-1" not in reid._lost


def test_loss_removes_active_mapping_and_copies_embedding():
    memory = InMemoryReID()
    embedding = np.array([1., 0.])
    person = memory.resolve(1, embedding, BBOX)
    memory.mark_lost(person, embedding)
    embedding[:] = [0., 1.]
    assert 1 not in memory._active
    assert memory.resolve(2, np.array([1., 0.]), BBOX) == person
    assert person not in memory._lost
    assert memory.resolve(3, np.array([1., 0.]), BBOX) != person


def test_active_resolve_also_purges_expired_entries(monkeypatch):
    now = [0.]
    monkeypatch.setattr(memory_reid.time, 'monotonic', lambda: now[0])
    memory = InMemoryReID()
    person = memory.resolve(1, np.array([1., 0.]), BBOX)
    memory.mark_lost('old', np.array([0., 1.]))
    now[0] = 60
    assert memory.resolve(1, np.array([1., 0.]), BBOX) == person
    assert memory._lost == {}


def test_session_memory_survives_long_absence(monkeypatch):
    now = [0.]
    monkeypatch.setattr(memory_reid.time, 'monotonic', lambda: now[0])
    memory = InMemoryReID(ttl_seconds=0)
    person = memory.resolve(1, np.array([1., 0.]), BBOX)
    memory.mark_lost(person, np.array([1., 0.]))
    now[0] += 3 * 60 * 60
    assert memory.resolve(2, np.array([1., 0.]), BBOX) == person


def test_gallery_recovers_front_view_after_last_seen_from_back():
    memory = InMemoryReID(ttl_seconds=0)
    person = memory.resolve(1, np.array([1., 0.]), BBOX)
    assert memory.resolve(1, np.array([0., 1.]), BBOX) == person
    memory.mark_lost(person, np.array([0., 1.]))
    assert memory.resolve(2, np.array([1., 0.]), BBOX) == person


def test_ambiguous_new_track_does_not_merge_two_people():
    memory = InMemoryReID(ttl_seconds=0)
    first = memory.resolve(1, np.array([1., 0.]), BBOX)
    second = memory.resolve(2, np.array([1., 0.]), BBOX)
    assert first != second
    memory.mark_lost(first, np.array([1., 0.]))
    memory.mark_lost(second, np.array([1., 0.]))
    assert memory.resolve(3, np.array([1., 0.]), BBOX) not in {first, second}


def test_retained_tracker_id_disambiguates_an_occlusion():
    memory = InMemoryReID()
    first = memory.resolve(1, np.array([1., 0.]), BBOX)
    second = memory.resolve(2, np.array([1., 0.]), BBOX)
    memory.mark_lost(first, np.array([1., 0.]))
    memory.mark_lost(second, np.array([1., 0.]))
    assert memory.resolve(2, np.array([1., 0.]), BBOX) == second
    assert memory.resolve(1, np.array([1., 0.]), BBOX) == first


def test_application_defaults_to_session_memory(monkeypatch):
    monkeypatch.delenv('VISION_CORE_REID_TTL_SECONDS', raising=False)
    assert InMemoryReID.from_env().ttl_seconds == 0
    monkeypatch.setenv('VISION_CORE_REID_TTL_SECONDS', '1800')
    assert InMemoryReID.from_env().ttl_seconds == 1800


def test_visible_retained_track_is_reserved_before_new_detections():
    memory = InMemoryReID()
    original = memory.resolve(1, np.array([1., 0.]), BBOX)
    memory.mark_lost(original, np.array([1., 0.]))
    memory.begin_frame({1, 2})
    assert memory.resolve(2, np.array([1., 0.]), BBOX) != original
    assert memory.resolve(1, np.array([1., 0.]), BBOX) == original
