from dataclasses import FrozenInstanceError

import pytest

from vision_core.features.door.application.dto.request.request_get_history import RequestGetHistory
from vision_core.features.door.application.dto.request.request_update import RequestUpdate
from vision_core.features.door.application.dto.response.response_get_history import ResponseGetHistory
from vision_core.features.door.application.dto.response.response_update import ResponseUpdate


def test_door_dtos_are_immutable():
    requests = [RequestUpdate("person-1", (1.0, 2.0)), RequestGetHistory("person-1")]
    responses = [ResponseUpdate(None), ResponseGetHistory(())]

    for dto in requests + responses:
        with pytest.raises(FrozenInstanceError):
            dto.person_id = "other"
