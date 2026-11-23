from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CameraQualitySettings:
    enabled: bool = True
    sample_every_n_frames: int = 15
    frozen_frames: int = 30
    frozen_difference: float = 1.0
    min_blur_variance: float = 50.0
    min_brightness: float = 25.0
    max_brightness: float = 230.0
    check_resolution: bool = True
    check_frozen: bool = True
    check_blur: bool = True
    check_exposure: bool = True
    check_zones: bool = True
