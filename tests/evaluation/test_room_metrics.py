import pytest

from vision_core.scripts.evaluate_room import evaluate


def detection(track, x=0):
    return {'track_id': track, 'bbox': {'x1': x, 'y1': 0, 'x2': x + 10, 'y2': 10}}


def test_metrics_misses_false_positives_and_identity_changes():
    rows = [{'kind': 'detections', 'frame': 1, 'detections': [detection(1), detection(9, 30)]},
            {'kind': 'resolved', 'frame': 1, 'persons': {'1': 'alice'}},
            {'kind': 'detections', 'frame': 2, 'detections': []},
            {'kind': 'detections', 'frame': 3, 'detections': [detection(2)]},
            {'kind': 'resolved', 'frame': 3, 'persons': {'2': 'alice'}}]
    truth = [{'frame': i, 'persons': [{'id': 'A', 'bbox': [0, 0, 10, 10]}]} for i in (1, 2, 3)]
    result = evaluate(rows, truth)
    assert result["true_positives"] == 2
    assert result["false_positives"] == result["missed_detections"] == 1
    assert result["precision"] == result["recall"] == pytest.approx(2 / 3)
    assert result["local_id_changes"] == 1
    assert result["person_id_changes"] == 0
    rows[-1]["persons"]["2"] = "bob"
    assert evaluate(rows, truth)["person_id_changes"] == 1


def test_missing_frame_is_not_silent_false_negative():
    with pytest.raises(ValueError):
        evaluate([], [{'frame': 1, 'persons': []}])


def test_one_detection_cannot_match_two_people():
    result = evaluate([{'kind': 'detections', 'frame': 1, 'detections': [detection(1)]}],
        [{'frame': 1, 'persons': [{'id': str(i), 'bbox': [0, 0, 10, 10]} for i in range(2)]}])
    assert result['true_positives'] == result['missed_detections'] == 1
    assert result['person_id_changes'] is None
