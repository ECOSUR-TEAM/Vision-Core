"""Group tensor -> numpy conversions when reading YOLO prediction boxes."""

import numpy as np


def _as_numpy(value):
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    return np.asarray(value)


def iter_prediction_boxes(result):
    """Yield ``(class_id, confidence, xyxy)`` with at most three GPU syncs.

    Ultralytics exposes batched tensors, so one conversion per attribute is
    enough. The fallback keeps compatibility with lightweight adapters and
    test doubles that iterate per-box numpy arrays.
    """
    boxes = result.boxes
    if all(hasattr(boxes, name) for name in ("xyxy", "conf", "cls")):
        xyxy = _as_numpy(boxes.xyxy)
        confidence = _as_numpy(boxes.conf)
        classes = _as_numpy(boxes.cls)
        for index in range(len(xyxy)):
            yield float(classes[index]), float(confidence[index]), xyxy[index]
        return
    for box in boxes:
        yield float(box.cls[0]), float(box.conf[0]), _as_numpy(box.xyxy[0])
