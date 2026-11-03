"""Create a synthetic video from the packaged Ultralytics bus image; not room footage."""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np
import ultralytics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', help='Directorio nuevo para los archivos')
    args = parser.parse_args()
    folder = Path(args.directory)
    folder.mkdir(parents=True, exist_ok=False)
    image = cv2.imread(str(Path(ultralytics.__file__).parent / 'assets/bus.jpg'))
    if image is None:
        raise RuntimeError('La instalación de Ultralytics no incluye bus.jpg')
    h, w = image.shape[:2]
    writer = cv2.VideoWriter(str(folder/'sample.avi'), cv2.VideoWriter_fourcc(*'MJPG'), 10, (w,h))
    if not writer.isOpened():
        raise RuntimeError('No se pudo crear el video MJPEG')
    try:
        for shift in list(range(0,151,10)) + [150]*3 + list(range(150,-1,-10)):
            writer.write(cv2.warpAffine(image, np.float32([[1,0,shift],[0,1,0]]), (w,h)))
    finally:
        writer.release()
    (folder/'zones.json').write_text(json.dumps({
        'frame_size': [w,h], 'door': [[190,0],[210,0],[210,h-1],[190,h-1]],
        'exterior': [[0,0],[200,0],[200,h-1],[0,h-1]],
        'interior': [[200,0],[w-1,0],[w-1,h-1],[200,h-1]],
    }, indent=2))


if __name__ == '__main__':
    main()
