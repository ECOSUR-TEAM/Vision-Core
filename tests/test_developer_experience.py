import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_makefile_has_reproducible_commands():
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    for target in ("setup", "test", "lint", "format", "run", "docker-build"):
        assert f"{target}:" in makefile


def test_devcontainer_recommends_python_ruff_and_docker():
    config = json.loads((ROOT / ".devcontainer/devcontainer.json").read_text(encoding="utf-8"))
    extensions = config["customizations"]["vscode"]["extensions"]
    assert "ms-python.python" in extensions
    assert "charliermarsh.ruff" in extensions
    assert "ms-azuretools.vscode-docker" in extensions


def test_compose_defines_camera_webcam_and_synthetic_profiles():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    profiles = {profile for service in compose["services"].values() for profile in service.get("profiles", [])}
    assert {"camera", "synthetic", "file"} <= profiles

    webcam = yaml.safe_load((ROOT / "docker-compose.webcam.yml").read_text(encoding="utf-8"))
    assert any("webcam" in service.get("profiles", []) for service in webcam["services"].values())


def test_synthetic_generator_and_zones_are_documented():
    assert (ROOT / "src/vision_core/scripts/create_pipeline_sample.py").is_file()
    assert (ROOT / "dev-data/zones.json").is_file()
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "create_pipeline_sample" in makefile
