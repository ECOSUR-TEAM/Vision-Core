import ast
from dataclasses import is_dataclass
from pathlib import Path

from vision_core.features.video.application.dto.request.request_close_video import (
    RequestCloseVideo,
)
from vision_core.features.video.application.dto.request.request_open_video import (
    RequestOpenVideo,
)
from vision_core.features.video.application.dto.request.request_read_frame import (
    RequestReadFrame,
)
from vision_core.features.video.application.dto.response.response_close_video import (
    ResponseCloseVideo,
)
from vision_core.features.video.application.dto.response.response_open_video import (
    ResponseOpenVideo,
)
from vision_core.features.video.application.dto.response.response_read_frame import (
    ResponseReadFrame,
)

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


def test_dtos_are_frozen_and_slotted():
    for dto in DTO_CLASSES:
        assert is_dataclass(dto)
        assert dto.__dataclass_params__.frozen is True
        assert hasattr(dto, "__slots__")


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
