"""Pruebas del generador determinista de video sintético."""

import json

from vision_core.scripts.create_benchmark_video import build_scene, write_benchmark_video


def test_generator_is_reproducible(tmp_path):
    first = write_benchmark_video(tmp_path / "a", frames=30, fps=15, width=320, height=240)
    second = write_benchmark_video(tmp_path / "b", frames=30, fps=15, width=320, height=240)
    assert first == second
    assert first["frames"] == 30
    assert (tmp_path / "a" / "benchmark.avi").stat().st_size > 0
    scene = json.loads((tmp_path / "a" / "scene.json").read_text(encoding="utf-8"))
    assert len(scene["entries"]) == 30
    assert {entry["marker"] for entry in scene["entries"]} == {"normal", "outside"}
    assert (tmp_path / "a" / "zones.json").is_file()


def test_build_scene_keeps_stable_tracks_and_losses():
    scene = build_scene(45, 15, 320, 240)
    entries = scene["entries"]
    assert [entry["track_id"] for entry in entries[:10]] == [1] * 10
    assert [entry["track_id"] for entry in entries[10:20]] == [2] * 10
    assert entries[10]["lost_ids"] == [1]
    assert entries[0]["lost_ids"] == []
