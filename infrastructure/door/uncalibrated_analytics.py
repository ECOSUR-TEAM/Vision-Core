"""No room crossings until actual camera zones have been calibrated."""
from domain.ports import DoorAnalytics


class UncalibratedAnalytics(DoorAnalytics):
    def update(self, person_id, position):
        return None

    def get_history(self, person_id):
        return ()
