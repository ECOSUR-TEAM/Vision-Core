from domain.attendance import SessionAttendance
from domain.entities import Event


def test_leave_and_return_is_one_visitor_but_restores_occupancy():
    attendance = SessionAttendance()
    first = attendance.apply(Event('PERSON_ENTERED', 'person-1'))
    assert first == dict(returning_person=False, unique_people_entered=1, people_inside=1)
    assert attendance.apply(Event('PERSON_EXITED', 'person-1'))['people_inside'] == 0
    returned = attendance.apply(Event('PERSON_ENTERED', 'person-1'))
    assert returned == dict(returning_person=True, unique_people_entered=1, people_inside=1)
    another = attendance.apply(Event('PERSON_ENTERED', 'person-2'))
    assert another['unique_people_entered'] == 2
    assert another['people_inside'] == 2
    assert attendance.apply(Event('PERSON_ENTERED', 'person-2'))['people_inside'] == 2
    assert attendance.apply(Event('PERSON_EXITED', 'unknown'))['people_inside'] == 2
