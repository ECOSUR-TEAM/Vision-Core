import numpy as np

from domain.entities import Detection
from domain.ports import DetectorManager

PERSON_CLASS_ID = 0  # COCO
CONFIDENCE_THRESHOLD = 0.5


class YoloDetectorManager(DetectorManager):
    """VC-DETECT (Carlos + Ameth).

    TODO:
    - Cargar YOLOv8 (nano/small) en __init__.
    - En process(): inferir, filtrar class_id == PERSON_CLASS_ID y
      confidence > CONFIDENCE_THRESHOLD.
    - Pasar las cajas resultantes a ByteTrack/Norfair para obtener track_id.
    - Devolver list[Detection].
    """

    def __init__(self, model_path: str = "yolov8n.pt") -> None:
        self._model_path = model_path
        # self._model = YOLO(model_path)
        # self._tracker = ...  # ByteTrack / Norfair

    def process(self, frame: np.ndarray) -> list[Detection]:
        raise NotImplementedError
