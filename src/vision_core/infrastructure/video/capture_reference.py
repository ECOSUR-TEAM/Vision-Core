"""Save one full-resolution frame from Frigate without a browser."""

import argparse
from pathlib import Path

import cv2

from vision_core.composition import build_video_with


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", help="Nuevo archivo PNG")
    args = parser.parse_args()
    path = Path(args.output)
    if path.suffix.lower() != ".png" or path.exists():
        parser.error("Usa un archivo .png nuevo")
    video = build_video_with()
    try:
        video.open()
        frame = video.read_frame()
        if frame is None:
            raise RuntimeError("No se recibió un frame")
        ok, encoded = cv2.imencode(".png", frame)
        if not ok:
            raise RuntimeError("No se pudo codificar el frame")
        with path.open("xb") as output:
            output.write(encoded.tobytes())
        print(f"Frame guardado: {frame.shape[1]} × {frame.shape[0]} píxeles")
    finally:
        video.close()


if __name__ == "__main__":
    main()
