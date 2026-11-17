from enum import Enum


class EventType(str, Enum):
    PERSON_ENTERED = "PERSON_ENTERED"
    PERSON_EXITED = "PERSON_EXITED"
    FALSE_ALARM = "FALSE_ALARM"
