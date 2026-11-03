from pathlib import Path
import cv2
from domain.ports import VideoSource
from .frame_validation import validate_frame


class FileVideoSource(VideoSource):
    """Replay a local recording; unlike RTSP, EOF is expected."""
    def __init__(self, path):
        self.path = Path(path)
        self._cap = None

    def open(self):
        self.close()
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        self._cap = cv2.VideoCapture(str(self.path))
        if not self._cap.isOpened():
            self.close()
            raise ConnectionError('No se pudo abrir el video grabado')

    def read_frame(self):
        if self._cap is None:
            raise RuntimeError('Llama a open() antes de read_frame()')
        ok, frame = self._cap.read()
        if not ok:
            return None
        validate_frame(frame)
        return frame

    def close(self):
        cap, self._cap = self._cap, None
        if cap is not None:
            cap.release()
