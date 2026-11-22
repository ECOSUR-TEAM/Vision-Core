"""Configuration flags for sequential inference and optional rendering."""

import os
from dataclasses import dataclass

from vision_core.core.config.settings_helpers import parse_bool


def env_flag(name: str, default: str) -> bool:
    """Parse a boolean environment flag with one canonical interpretation."""
    parsed = parse_bool(name, os.getenv(name, default), False)
    if parsed is None:
        raise ValueError(f"{name} debe ser 1/0, true/false, yes/no u on/off")
    return parsed


def _positive_int(name: str, default: str) -> int:
    raw = os.getenv(name, default).strip()
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} debe ser un entero positivo") from error
    if value < 1:
        raise ValueError(f"{name} debe ser un entero positivo")
    return value


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    """Flags de bajo riesgo; no cambian el modelo ni la lógica de tracking.

    ``embedding_batch_size`` y ``embedding_frame_stride`` preparan las
    optimizaciones futuras (batching multi-crop / salto de embeddings). Hoy el
    pipeline mantiene una inferencia por detección para no alterar ReID.
    """

    render_enabled: bool = True
    embedding_batch_size: int = 1
    embedding_frame_stride: int = 1
    profiling_enabled: bool = False
    profiling_output: str = "profiling_results.json"

    def __post_init__(self) -> None:
        for name in ("embedding_batch_size", "embedding_frame_stride"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{name} debe ser un entero positivo")
        if not self.profiling_output:
            raise ValueError("profiling_output no puede estar vacío")

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        return cls(
            render_enabled=env_flag("VISION_CORE_RENDER_ENABLED", "1"),
            embedding_batch_size=_positive_int("VISION_CORE_EMBEDDING_BATCH_SIZE", "1"),
            embedding_frame_stride=_positive_int("VISION_CORE_EMBEDDING_STRIDE", "1"),
            profiling_enabled=env_flag("VISION_CORE_PROFILING_ENABLED", "0"),
            profiling_output=os.getenv("VISION_CORE_PROFILING_OUTPUT", "profiling_results.json"),
        )
