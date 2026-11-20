from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RequestRunPipeline:
    expected_frame_size: tuple[int, int] | None = None
