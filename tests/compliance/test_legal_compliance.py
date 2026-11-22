import re
import sqlite3
from pathlib import Path

from vision_core.settings.persistence import (
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


def test_third_party_notices_inventory_and_agpl_decision():
    text = _read("THIRD_PARTY_NOTICES.md").lower()
    for component in ("ultralytics", "torch", "torchvision", "opencv-python", "numpy", "pillow", "pyyaml"):
        assert component in text
    assert "agpl-3.0" in text
    assert "licencia comercial" in text
    assert "corresponding source" in text


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
    assert "produce una advertencia" not in lowered
    assert "pendiente bloqueante" in lowered


def test_legal_review_is_registered_as_production_blocker():
    text = _read("docs/legal-review.md").lower()
    assert "pendiente" in text
    assert "bloqueante para producción" in text
    assert "asesoría legal externa" in text
    assert "agpl" in text
    assert "bloqueante" in text
    assert "no cerrado por ticket 42" in text


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


def test_privacy_retention_snippet_uses_real_columns_and_ttls():
    text = _read("docs/privacy-retention.md")
    match = re.search(r"```bash\npython - <<'PY'\n(?P<code>.*?)\nPY\n```", text, re.DOTALL)
    assert match, "No se encontró el snippet de verificación de borrado"
    code = match.group("code")

    assert "tracks" in code and "timestamp_utc" in code
    assert "updated_at_utc" not in code

    expected = {
        "events": ("timestamp_utc", 30 * 86400),
        "zone_observations": ("timestamp_utc", 7 * 86400),
        "tracks": ("timestamp_utc", 86400),
        "identity_gallery": ("last_seen_at_utc", 86400),
        "sessions": ("started_at_utc", 30 * 86400),
        "metrics": ("timestamp_utc", 30 * 86400),
    }
    checks_match = re.search(r"checks\s*=\s*\((?P<body>.*?)\)\nfor ", code, re.DOTALL)
    assert checks_match, "No se encontró la tabla de checks en el snippet"
    body = checks_match.group("body")
    found = {}
    for table, column, ttl in re.findall(r'\("([^"]+)",\s*"([^"]+)",\s*([^\)]+)\)', body):
        found[table] = (column, eval(ttl, {"__builtins__": {}}, {}))
    assert found == expected

    conn = sqlite3.connect(":memory:")
    migrations = ROOT / "src/vision_core/infrastructure/persistence/migrations"
    conn.executescript((migrations / "001_initial.sql").read_text(encoding="utf-8"))
    conn.executescript((migrations / "002_metrics.sql").read_text(encoding="utf-8"))
    for table, (column, _) in expected.items():
        conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} < ?", (0.0,)).fetchone()
    conn.close()
