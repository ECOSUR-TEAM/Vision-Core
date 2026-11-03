"""Validate coordinates and render an overlay on the original camera frame."""
import argparse
from pathlib import Path
import cv2
import numpy as np
from .zone_config import load_zones


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('frame')
    parser.add_argument('config')
    parser.add_argument('output', help='Nuevo archivo PNG con los polígonos')
    args = parser.parse_args()
    zones = load_zones(args.config)
    frame = cv2.imread(args.frame)
    if frame is None or frame.shape[:2] != (zones.height, zones.width):
        parser.error('El frame no existe o su resolución no coincide con frame_size')
    path = Path(args.output)
    if path.exists() or path.suffix.lower() != '.png':
        parser.error('Usa un archivo .png nuevo')
    for polygon, color in [(zones.exterior, (255, 180, 0)), (zones.interior, (0, 200, 0)),
                            (zones.door, (0, 0, 255))]:
        points = np.rint(polygon.points).astype(np.int32)
        cv2.polylines(frame, [points], True, color, 2)
        for i, point in enumerate(points):
            cv2.circle(frame, tuple(point), 3, color, -1)
            cv2.putText(frame, f'{polygon.name}:{i}', tuple(point), cv2.FONT_HERSHEY_SIMPLEX, .4, color, 1)
    ok, encoded = cv2.imencode('.png', frame)
    if not ok:
        raise RuntimeError('No se pudo codificar la imagen')
    with path.open('xb') as output:
        output.write(encoded.tobytes())


if __name__ == '__main__':
    main()
