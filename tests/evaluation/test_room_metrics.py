import pytest
from scripts.evaluate_room import evaluate


def detection(track, x=0):
    return dict(track_id=track, bbox=dict(x1=x,y1=0,x2=x+10,y2=10))


def test_metrics_misses_false_positives_and_identity_changes():
    rows = [dict(kind='detections', frame=1, detections=[detection(1),detection(9,30)]),
            dict(kind='resolved', frame=1, persons={'1':'alice'}),
            dict(kind='detections', frame=2, detections=[]),
            dict(kind='detections', frame=3, detections=[detection(2)]),
            dict(kind='resolved', frame=3, persons={'2':'alice'})]
    truth = [dict(frame=i,persons=[dict(id='A',bbox=[0,0,10,10])]) for i in (1,2,3)]
    result = evaluate(rows, truth)
    assert result['true_positives'] == 2
    assert result['false_positives'] == result['missed_detections'] == 1
    assert result['precision'] == result['recall'] == pytest.approx(2/3)
    assert result['local_id_changes'] == 1
    assert result['person_id_changes'] == 0
    rows[-1]['persons']['2'] = 'bob'
    assert evaluate(rows, truth)['person_id_changes'] == 1


def test_missing_frame_is_not_silent_false_negative():
    with pytest.raises(ValueError):
        evaluate([], [dict(frame=1,persons=[])])


def test_one_detection_cannot_match_two_people():
    result = evaluate([dict(kind='detections',frame=1,detections=[detection(1)])],
        [dict(frame=1, persons=[dict(id=str(i),bbox=[0,0,10,10]) for i in range(2)])])
    assert result['true_positives'] == result['missed_detections'] == 1
    assert result['person_id_changes'] is None
