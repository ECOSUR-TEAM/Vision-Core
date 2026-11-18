from dataclasses import dataclass

import numpy as np


@dataclass
class _Track:
    bbox: np.ndarray
    velocity: np.ndarray
    missed: int = 0

    def predict(self) -> np.ndarray:
        return self.bbox + self.velocity * (self.missed + 1)
