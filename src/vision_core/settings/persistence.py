import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_EVENT_TTL_SECONDS = 30 * 24 * 3600
DEFAULT_HISTORY_TTL_SECONDS = 7 * 24 * 3600
DEFAULT_IDENTITY_TTL_SECONDS = 24 * 3600
DEFAULT_TRACK_TTL_SECONDS = 24 * 3600
DEFAULT_SESSION_TTL_SECONDS = 30 * 24 * 3600
DEFAULT_METRICS_TTL_SECONDS = 30 * 24 * 3600
DEFAULT_PRUNE_INTERVAL_SECONDS = 3600
DEFAULT_BUSY_TIMEOUT_SECONDS = 5.0


def _boolean(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _number(value: str | None, default: float, *, name: str, minimum: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        parsed = float(value)
    except ValueError as error:
        raise ValueError(f"{name} debe ser numérico") from error
    if parsed < minimum:
        raise ValueError(f"{name} debe ser >= {minimum}")
    return parsed


@dataclass(frozen=True, slots=True)
class PersistenceSettings:
    enabled: bool
    db_path: Path
    db_url: str | None
    password: str | None
    busy_timeout_seconds: float
    fail_open: bool
    event_ttl_seconds: float
    history_ttl_seconds: float
    identity_ttl_seconds: float
    track_ttl_seconds: float
    session_ttl_seconds: float
    metrics_ttl_seconds: float
    prune_interval_seconds: float

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "PersistenceSettings":
        env = os.environ if environ is None else environ
        raw_path = (env.get("VISION_CORE_DB_PATH") or "").strip()
        path = Path(raw_path).expanduser() if raw_path else Path("vision-core.sqlite3")
        enabled = _boolean(env.get("VISION_CORE_DB_ENABLED"), bool(raw_path))
        prune = _number(
            env.get("VISION_CORE_DB_PRUNE_INTERVAL_SECONDS"),
            DEFAULT_PRUNE_INTERVAL_SECONDS,
            name="VISION_CORE_DB_PRUNE_INTERVAL_SECONDS",
            minimum=1.0,
        )
        busy = _number(
            env.get("VISION_CORE_DB_BUSY_TIMEOUT_SECONDS"),
            DEFAULT_BUSY_TIMEOUT_SECONDS,
            name="VISION_CORE_DB_BUSY_TIMEOUT_SECONDS",
            minimum=0.0,
        )
        return cls(
            enabled=enabled,
            db_path=path,
            db_url=env.get("VISION_CORE_DB_URL") or None,
            password=env.get("VISION_CORE_DB_PASSWORD") or None,
            busy_timeout_seconds=busy,
            fail_open=_boolean(env.get("VISION_CORE_DB_FAIL_OPEN"), True),
            event_ttl_seconds=_number(
                env.get("VISION_CORE_EVENT_TTL_SECONDS"),
                DEFAULT_EVENT_TTL_SECONDS,
                name="VISION_CORE_EVENT_TTL_SECONDS",
            ),
            history_ttl_seconds=_number(
                env.get("VISION_CORE_HISTORY_TTL_SECONDS"),
                DEFAULT_HISTORY_TTL_SECONDS,
                name="VISION_CORE_HISTORY_TTL_SECONDS",
            ),
            identity_ttl_seconds=_number(
                env.get("VISION_CORE_IDENTITY_TTL_SECONDS"),
                DEFAULT_IDENTITY_TTL_SECONDS,
                name="VISION_CORE_IDENTITY_TTL_SECONDS",
            ),
            track_ttl_seconds=_number(
                env.get("VISION_CORE_TRACK_TTL_SECONDS"),
                DEFAULT_TRACK_TTL_SECONDS,
                name="VISION_CORE_TRACK_TTL_SECONDS",
            ),
            session_ttl_seconds=_number(
                env.get("VISION_CORE_SESSION_TTL_SECONDS"),
                DEFAULT_SESSION_TTL_SECONDS,
                name="VISION_CORE_SESSION_TTL_SECONDS",
            ),
            metrics_ttl_seconds=_number(
                env.get("VISION_CORE_METRICS_TTL_SECONDS"),
                DEFAULT_METRICS_TTL_SECONDS,
                name="VISION_CORE_METRICS_TTL_SECONDS",
            ),
            prune_interval_seconds=prune,
        )
