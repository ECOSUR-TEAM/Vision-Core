import numpy as np


def iou(first: np.ndarray, second: np.ndarray) -> float:
    intersection = np.maximum(
        np.minimum(first[2:], second[2:]) - np.maximum(first[:2], second[:2]), 0
    ).prod()
    union = (
        np.maximum(first[2:] - first[:2], 0).prod()
        + np.maximum(second[2:] - second[:2], 0).prod()
        - intersection
    )
    return float(intersection / union) if union > 0 else 0.0
