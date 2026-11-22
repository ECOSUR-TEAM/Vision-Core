"""Genera un video sintético determinista y sus zonas para el benchmark."""

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from vision_core.scripts.benchmark_metadata import GENERATOR_VERSION, VIDEO_SEED

PATTERN = (
    ("normal", 60),
    ("normal", 160),
    ("normal", 170),
    ("normal", 60),
    ("normal", 70),
    ("outside", -5),
    ("normal", 60),
    ("normal", 160),
    ("normal", 170),
    ("normal", 60),
)


def build_scene(frames: int, fps: int, width: int, height: int) -> dict:
    if frames < 1 or fps < 1 or width < 320 or height < 240:
        raise ValueError("Se requieren frames>=1, fps>=1, width>=320 y height>=240")
    entries = []
    for index in range(frames):
        marker, x = PATTERN[index % len(PATTERN)]
        chunk = index // len(PATTERN)
        entries.append(
            {
                "frame": index,
                "marker": marker,
                "x": x,
                "y": 120,
                "track_id": chunk + 1,
                "lost_ids": [chunk] if marker == "normal" and index % len(PATTERN) == 0 and chunk > 0 else [],
            }
        )
    return {
        "version": 1,
        "generator_version": GENERATOR_VERSION,
        "seed": VIDEO_SEED,
        "frames": frames,
        "fps": fps,
        "width": width,
        "height": height,
        "entries": entries,
    }


def _zones(width: int, height: int) -> dict:
    return {
        "version": "1.0",
        "frame_size": [width, height],
        "door": [[120, 0], [140, 0], [140, height - 1], [120, height - 1]],
        "exterior": [[0, 0], [120, 0], [120, height - 1], [0, height - 1]],
        "interior": [[140, 0], [width - 1, 0], [width - 1, height - 1], [140, height - 1]],
    }


def _frame(width: int, height: int, marker: str, x: int) -> np.ndarray:
    yy, xx = np.mgrid[0:height, 0:width]
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, :, 0] = ((xx + 2 * yy) % 64).astype(np.uint8)
    frame[:, :, 1] = ((3 * xx + yy) % 64).astype(np.uint8)
    frame[:, :, 2] = ((xx + yy) % 48).astype(np.uint8)
    color = (0, 0, 255) if marker == "outside" else (255, 255, 255)
    cv2.rectangle(frame, (x - 10, 100), (x + 10, 140), color, -1)
    return frame


def write_benchmark_video(
    directory: str | Path,
    *,
    frames: int,
    fps: int,
    width: int,
    height: int,
    allow_existing: bool = False,
) -> dict:
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    video_path = folder / "benchmark.avi"
    scene_path = folder / "scene.json"
    zones_path = folder / "zones.json"
    manifest_path = folder / "manifest.json"
    targets = (video_path, scene_path, zones_path, manifest_path)
    if not allow_existing and any(path.exists() for path in targets):
        raise FileExistsError(f"Ya existen artefactos en {folder}; usa --allow-existing para regenerarlos")

    scene = build_scene(frames, fps, width, height)
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter.fourcc(*"MJPG"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError("No se pudo crear el video MJPEG del benchmark")
    try:
        for entry in scene["entries"]:
            writer.write(_frame(width, height, entry["marker"], entry["x"]))
    finally:
        writer.release()

    scene_bytes = json.dumps(scene, indent=2, sort_keys=True).encode("utf-8")
    scene_path.write_bytes(scene_bytes)
    zones_path.write_text(json.dumps(_zones(width, height), indent=2) + "\n", encoding="utf-8")
    manifest = {
        "generator": "create_benchmark_video",
        "generator_version": GENERATOR_VERSION,
        "seed": VIDEO_SEED,
        "frames": frames,
        "fps": fps,
        "width": width,
        "height": height,
        "video_sha256": hashlib.sha256(video_path.read_bytes()).hexdigest(),
        "scene_sha256": hashlib.sha256(scene_bytes).hexdigest(),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", help="Directorio donde se escriben los artefactos")
    parser.add_argument("--frames", type=int, default=450, help="Frames a generar (30 s a 15 fps por defecto)")
    parser.add_argument("--fps", type=int, default=15)
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=240)
    parser.add_argument("--allow-existing", action="store_true")
    args = parser.parse_args()
    manifest = write_benchmark_video(
        args.directory,
        frames=args.frames,
        fps=args.fps,
        width=args.width,
        height=args.height,
        allow_existing=args.allow_existing,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
