import re
import sqlite3
import tomllib
from pathlib import Path

from vision_core.core.config.persistence import (
    DEFAULT_EVENT_TTL_SECONDS,
    DEFAULT_HISTORY_TTL_SECONDS,
    DEFAULT_IDENTITY_TTL_SECONDS,
    DEFAULT_METRICS_TTL_SECONDS,
    DEFAULT_SESSION_TTL_SECONDS,
    DEFAULT_TRACK_TTL_SECONDS,
    PersistenceSettings,
)

ROOT = Path(__file__).resolve().parents[2]


def _read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def _setuptools_requirement():
    document = tomllib.loads(_read("pyproject.toml"))
    for requirement in document["build-system"]["requires"]:
        if requirement.startswith("setuptools"):
            return requirement.removeprefix("setuptools")
    raise AssertionError("setuptools no está declarado en build-system.requires")


def _requirements_versions(relative):
    versions = {}
    for line in _read(relative).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("-", "#")):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)==([^\s;]+)", stripped)
        if match:
            versions[match.group(1).lower()] = match.group(2)
    return versions


def _setuptools_requirement():
    pyproject = tomllib.loads(_read("pyproject.toml"))
    for requirement in pyproject["build-system"]["requires"]:
        if requirement.lower().startswith("setuptools"):
            return requirement[len("setuptools") :]
    raise AssertionError("setuptools no está declarado en build-system.requires")


def test_third_party_notices_match_requirements_and_gate_agpl_publication():
    text = _read("THIRD_PARTY_NOTICES.md")
    lowered = text.lower()
    for component in ("ultralytics", "torch", "torchvision", "opencv-python", "numpy", "pillow", "pyyaml"):
        assert component in lowered
    assert "agpl-3.0" in lowered
    assert "licencia comercial" in lowered
    assert "corresponding source" in lowered

    rows = {
        name.strip().lower(): version.strip()
        for name, version in re.findall(r"^\| ([^|]+?) \| ([^|]+?) \|", text, re.MULTILINE)
    }
    expected = {}
    for requirements in ("requirements.txt", "requirements-cpu.txt", "requirements-dev.txt"):
        expected.update(_requirements_versions(requirements))
    for name, version in expected.items():
        assert name in rows, f"Falta {name} en THIRD_PARTY_NOTICES.md"
        assert rows[name] == version, f"Versión incorrecta para {name}: {rows[name]} != {version}"

    for tool, version in (("setuptools", _setuptools_requirement()), ("ruff", "0.3.0")):
        assert rows.get(tool) == version, f"Falta la herramienta {tool} {version}"

    workflow = _read(".github/workflows/docker.yml")
    assert "vars.PUBLISH_CONTAINER_IMAGES == 'true'" in workflow
    assert re.search(r"push:\s*true", workflow)


def test_privacy_policy_documents_purpose_flow_retention_and_requests():
    text = _read("docs/privacy-retention.md")
    lowered = text.lower()
    for section in ("finalidad", "base legal", "señal", "minimización", "flujo de datos", "retención"):
        assert section in lowered
    assert "```mermaid" in text
    for variable in (
        "VISION_CORE_EVENT_TTL_SECONDS",
        "VISION_CORE_HISTORY_TTL_SECONDS",
        "VISION_CORE_IDENTITY_TTL_SECONDS",
        "VISION_CORE_TRACK_TTL_SECONDS",
        "VISION_CORE_SESSION_TTL_SECONDS",
        "VISION_CORE_METRICS_TTL_SECONDS",
    ):
        assert variable in text
    assert "VISION_CORE_DB_ENABLED" in text
    assert "solicitar acceso" in lowered
    assert "riesgos y pendientes" in lowered
    assert "person_id" in lowered
    assert "datos biométricos" in lowered
    assert "Dockerfile" in text
    assert "0.0.0.0" in text
    assert "no debe afirmarse" in text
    assert "escucha en localhost" in text
    assert "pendiente de implementar antes de producción" in lowered
    assert "pendiente bloqueante" in lowered


def test_legal_review_is_registered_as_production_blocker():
    text = _read("docs/legal-review.md").lower()
    assert "pendiente" in text
    assert "bloqueante para producción" in text
    assert "asesoría legal externa" in text
    assert "agpl" in text
    assert "bloqueante" in text
    assert "no cerrado por ecm-87" in text
    assert "publish_container_images" in text
    assert "procedimiento de derechos" in text


def test_docs_index_links_legal_documents_and_review_row():
    text = _read("docs/README.md")
    assert "legal-review.md" in text
    assert "privacy-retention.md" in text
    assert "ECM-87" in text


def test_retention_defaults_match_documented_values():
    settings = PersistenceSettings.from_env({"VISION_CORE_DB_PATH": "vision-core.sqlite3"})
    assert settings.event_ttl_seconds == DEFAULT_EVENT_TTL_SECONDS == 30 * 86400
    assert settings.history_ttl_seconds == DEFAULT_HISTORY_TTL_SECONDS == 7 * 86400
    assert settings.identity_ttl_seconds == DEFAULT_IDENTITY_TTL_SECONDS == 86400
    assert settings.track_ttl_seconds == DEFAULT_TRACK_TTL_SECONDS == 86400
    assert settings.session_ttl_seconds == DEFAULT_SESSION_TTL_SECONDS == 30 * 86400
    assert settings.metrics_ttl_seconds == DEFAULT_METRICS_TTL_SECONDS == 30 * 86400


def test_retention_is_configurable():
    settings = PersistenceSettings.from_env(
        {
            "VISION_CORE_DB_PATH": "vision-core.sqlite3",
            "VISION_CORE_EVENT_TTL_SECONDS": "3600",
            "VISION_CORE_IDENTITY_TTL_SECONDS": "0",
        }
    )
    assert settings.event_ttl_seconds == 3600
    assert settings.identity_ttl_seconds == 0


def test_privacy_retention_snippet_uses_real_columns_configured_ttls_and_current_paths():
    text = _read("docs/privacy-retention.md")
    match = re.search(r"```bash\npython - <<'PY'\n(?P<code>.*?)\nPY\n```", text, re.DOTALL)
    assert match, "No se encontró el snippet de verificación de borrado"
    code = match.group("code")

    assert "from vision_core.core.config.persistence import PersistenceSettings" in code
    assert "PersistenceSettings.from_env(dict(os.environ))" in code
    assert "for label, query, ttl in checks" in code
    assert "eval(" not in code
    assert 'f"SELECT' not in code
    assert "30 * 86400" not in code

    expected = {
        "events": ("timestamp_utc", "settings.event_ttl_seconds"),
        "zone_observations": ("timestamp_utc", "settings.history_ttl_seconds"),
        "tracks": ("timestamp_utc", "settings.track_ttl_seconds"),
        "identity_gallery": ("last_seen_at_utc", "settings.identity_ttl_seconds"),
        "persons": ("last_seen_utc", "settings.identity_ttl_seconds"),
        "sessions": ("started_at_utc", "settings.session_ttl_seconds"),
        "metrics": ("timestamp_utc", "settings.metrics_ttl_seconds"),
    }
    for table, (column, setting) in expected.items():
        query = f"SELECT COUNT(*) FROM {table} WHERE {column} < ?"
        assert f'("{table}", "{query}", {setting})' in code, f"Falta la comprobación de {table}"

    conn = sqlite3.connect(":memory:")
    migrations = ROOT / "src/vision_core/core/infrastructure/persistence/migrations"
    conn.executescript((migrations / "001_initial.sql").read_text(encoding="utf-8"))
    conn.executescript((migrations / "002_metrics.sql").read_text(encoding="utf-8"))
    for table, (column, _) in expected.items():
        query = f"SELECT COUNT(*) FROM {table} WHERE {column} < ?"
        conn.execute(query, (0.0,)).fetchone()
    conn.close()
