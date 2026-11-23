from collections.abc import Mapping
from dataclasses import dataclass

from vision_core.core.dto import JSONValue


@dataclass(frozen=True, slots=True)
class ResponseCameraQuality:
    status: str
    reason: str | None
    signals: Mapping[str, JSONValue]
