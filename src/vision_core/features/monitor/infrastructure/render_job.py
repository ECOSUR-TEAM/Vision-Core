"""Immutable render payload produced on the inference thread."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import numpy as np

from vision_core.features.monitor.infrastructure.render_track import RenderTrack


@dataclass(frozen=True, slots=True)
class RenderJob:
    """Todo lo que el renderer necesita, sin referencias mutables compartidas.

    ``capture`` se ejecuta en el hilo de inferencia: copia el array antes de
    publicarlo y congela tracks y metadatos para evitar carreras con el ciclo
    siguiente, que reutiliza el mismo buffer de video.
    """

    frame: np.ndarray
    tracks: tuple[RenderTrack, ...]
    zones: Any
    zone_by_person: Mapping[str, str]
    label_for: Callable[[str], str]
    demo: bool
    processing_ms: float
    dropped: int

    @classmethod
    def capture(
        cls,
        frame: np.ndarray,
        tracks,
        *,
        zones=None,
        zone_by_person: Mapping[str, str] | None = None,
        label_for: Callable[[str], str] | None = None,
        demo: bool = False,
        processing_ms: float = 0.0,
        dropped: int = 0,
    ) -> "RenderJob":
        if not isinstance(frame, np.ndarray):
            raise TypeError("El frame debe ser un ndarray BGR uint8")
        return cls(
            frame=frame.copy(),
            tracks=tuple(RenderTrack.from_track(track) for track in tracks),
            zones=zones,
            zone_by_person=MappingProxyType(dict(zone_by_person or {})),
            label_for=label_for or (lambda person_id: person_id),
            demo=bool(demo),
            processing_ms=float(processing_ms),
            dropped=int(dropped),
        )
