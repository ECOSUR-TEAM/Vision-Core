import ast
import json
from dataclasses import MISSING, FrozenInstanceError, asdict, fields, is_dataclass, replace
from pathlib import Path
from typing import get_type_hints

import numpy as np
import pytest

from vision_core.features.video.application.dto.request.request_close_video import RequestCloseVideo
from vision_core.features.video.application.dto.request.request_open_video import RequestOpenVideo
from vision_core.features.video.application.dto.request.request_read_frame import RequestReadFrame
from vision_core.features.video.application.dto.response.response_close_video import ResponseCloseVideo
from vision_core.features.video.application.dto.response.response_open_video import ResponseOpenVideo
from vision_core.features.video.application.dto.response.response_read_frame import ResponseReadFrame
from vision_core.features.video.application.mappers.video_mapper import dto_to_frame, frame_to_dto

ROOT = Path(__file__).resolve().parents[4]
DTO_DIR = ROOT / "src" / "vision_core" / "features" / "video" / "application" / "dto"
DTO_CLASSES = (
    RequestOpenVideo,
    RequestReadFrame,
    RequestCloseVideo,
    ResponseOpenVideo,
    ResponseReadFrame,
    ResponseCloseVideo,
)
FORBIDDEN = {"numpy", "cv2", "torch", "torchvision", "ultralytics"}


def test_request_fields_and_types():
    for dto in (RequestOpenVideo, RequestReadFrame, RequestCloseVideo):
        assert [field.name for field in fields(dto)] == []
        assert get_type_hints(dto) == {}


def test_response_fields_and_types():
    assert [field.name for field in fields(ResponseOpenVideo)] == ["opened"]
    assert get_type_hints(ResponseOpenVideo) == {"opened": bool}
    assert [field.name for field in fields(ResponseCloseVideo)] == ["closed"]
    assert get_type_hints(ResponseCloseVideo) == {"closed": bool}

    frame_png, width, height, image_format = fields(ResponseReadFrame)
    assert [field.name for field in fields(ResponseReadFrame)] == ["frame_png", "width", "height", "format"]
    assert get_type_hints(ResponseReadFrame) == {
        "frame_png": bytes | None,
        "width": int,
        "height": int,
        "format": str,
    }
    assert frame_png.default is MISSING and frame_png.default_factory is MISSING
    assert width.default == 0 and height.default == 0 and image_format.default == "png"


def test_dtos_are_frozen_and_slotted():
    for dto in DTO_CLASSES:
        assert is_dataclass(dto)
        assert dto.__dataclass_params__.frozen is True
        assert hasattr(dto, "__slots__")

    instances = (
        (ResponseOpenVideo(True), "opened"),
        (ResponseReadFrame(frame_png=None), "frame_png"),
        (ResponseCloseVideo(True), "closed"),
    )
    for dto, field in instances:
        with pytest.raises(FrozenInstanceError):
            setattr(dto, field, None)


def test_responses_are_json_serializable():
    assert json.loads(json.dumps(asdict(ResponseOpenVideo(True)), allow_nan=False)) == {"opened": True}
    assert json.loads(json.dumps(asdict(ResponseCloseVideo(True)), allow_nan=False)) == {"closed": True}

    response = replace(ResponseReadFrame(frame_png=None), width=5, height=3)
    payload = json.loads(json.dumps(asdict(response), allow_nan=False))

    assert payload == {"frame_png": None, "width": 5, "height": 3, "format": "png"}


def test_frame_response_round_trips_through_mapper():
    frame = np.zeros((3, 5, 3), dtype=np.uint8)

    assert np.array_equal(dto_to_frame(frame_to_dto(frame)), frame)


def test_dtos_do_not_import_external_frame_libraries():
    for path in DTO_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            assert not any(module.split(".")[0] in FORBIDDEN for module in modules), path
