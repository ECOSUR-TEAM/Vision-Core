import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from vision_core.infrastructure.monitor import __main__ as monitor_main

ROOT = Path(__file__).resolve().parents[3]
COMPOSE_FILES = (
    "docker-compose.yml",
    "docker-compose.monitor.yml",
    "docker-compose.webcam.yml",
    "docker-compose.camera.yml",
)


def _run_main(monkeypatch, argv):
    captured = {}
    monkeypatch.setattr(sys, "argv", argv)

    def fake_server(host, port, state):
        captured.update(host=host, port=port)
        return SimpleNamespace(
            shutdown=lambda: None,
            serve_forever=lambda **_: None,
            server_close=lambda: None,
        )

    monkeypatch.setattr(monitor_main, "make_server", fake_server)
    runtime = SimpleNamespace(
        failed=SimpleNamespace(is_set=lambda: False),
        start=lambda: None,
        stop=lambda: None,
        join=lambda **_: None,
    )
    monitor_main.main(state=object(), build_runtime=lambda *_args, **_kwargs: runtime)
    return captured


def test_local_start_binds_loopback_by_default(monkeypatch, capsys):
    monkeypatch.delenv("VISION_CORE_MONITOR_HOST", raising=False)
    captured = _run_main(monkeypatch, ["main.py", "--demo-zones"])
    output = capsys.readouterr().out
    assert captured["host"] == "127.0.0.1"
    assert "WARNING" not in output


@pytest.mark.parametrize("host", ["0.0.0.0", "0", ""])
def test_exposed_hosts_print_warning(monkeypatch, capsys, host):
    captured = _run_main(monkeypatch, ["main.py", "--demo-zones", "--host", host])
    output = capsys.readouterr().out
    assert captured["host"] == "0.0.0.0"
    assert "WARNING" in output
    assert "ticket 42" in output


def test_exposed_host_from_env_prints_warning(monkeypatch, capsys):
    monkeypatch.setenv("VISION_CORE_MONITOR_HOST", "0.0.0.0")
    captured = _run_main(monkeypatch, ["main.py", "--demo-zones"])
    output = capsys.readouterr().out
    assert captured["host"] == "0.0.0.0"
    assert "WARNING" in output
    assert "ticket 42" in output


@pytest.mark.parametrize("filename", COMPOSE_FILES)
def test_compose_publishes_only_on_loopback(filename):
    document = yaml.safe_load((ROOT / filename).read_text(encoding="utf-8")) or {}
    services = document.get("services") or {}
    published = []
    for service in services.values():
        for mapping in service.get("ports") or []:
            published.append(str(mapping))
            assert str(mapping).startswith("127.0.0.1:"), (filename, mapping)
    if filename in {"docker-compose.yml", "docker-compose.webcam.yml"}:
        assert published, f"{filename} should publish at least one port"


def test_dockerfile_any_host_is_explicit():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "ENV VISION_CORE_MONITOR_HOST=0.0.0.0" in dockerfile
    assert '"--host", "0.0.0.0"' in dockerfile


def test_exposure_documentation_warns_about_risk_and_ticket_42():
    doc = (ROOT / "docs" / "monitor-exposure.md").read_text(encoding="utf-8")
    assert "127.0.0.1" in doc
    assert "0.0.0.0" in doc
    assert "sin autenticación" in doc
    assert "ticket 42" in doc
