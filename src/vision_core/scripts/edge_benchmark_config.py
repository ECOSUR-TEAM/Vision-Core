import hashlib
import json
from pathlib import Path

from vision_core.core.config.settings_precision import is_supported_precision

SUPPORTED_SCHEMA_VERSION = 1
SUPPORTED_DEVICES = frozenset({"cpu", "cuda"})


def load_config(path: str | Path) -> dict:
    source = Path(path)
    try:
        config = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"No se pudo leer la configuración de benchmark: {source}") from error
    validate_config(config)
    return config


def validate_config(config: dict) -> None:
    if config.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        raise ValueError(f"schema_version debe ser {SUPPORTED_SCHEMA_VERSION}")
    for key in ("hardware_targets", "validation_set", "quality_gates", "profiles"):
        if not isinstance(config.get(key), (dict, list)) or not config[key]:
            raise ValueError(f"La configuración requiere '{key}' no vacío")
    gates = config["quality_gates"]
    for key in ("min_detection_map50", "min_identity_recall_at_1", "max_relative_drop_pct"):
        value = gates.get(key)
        if not isinstance(value, (int, float)) or not 0 <= value <= 100:
            raise ValueError(f"quality_gates.{key} debe estar entre 0 y 100")
    if gates.get("baseline_profile") not in {profile["id"] for profile in config["profiles"]}:
        raise ValueError("quality_gates.baseline_profile debe existir en profiles")
    profile_ids = set()
    for profile in config["profiles"]:
        for key in ("id", "target", "device"):
            if not profile.get(key):
                raise ValueError(f"profile.{key} es obligatorio")
        if profile["id"] in profile_ids:
            raise ValueError(f"id de perfil duplicado: {profile['id']}")
        if profile["target"] not in config["hardware_targets"]:
            raise ValueError(f"Target desconocido en perfil {profile['id']}: {profile['target']}")
        if profile["device"] not in SUPPORTED_DEVICES:
            raise ValueError(f"Dispositivo no soportado en perfil {profile['id']}: {profile['device']}")
        for role in ("detection", "embedding"):
            variant = profile.get(role, {})
            for key in ("model_id", "selector", "precision"):
                if not variant.get(key):
                    raise ValueError(f"profile.{profile['id']}.{role}.{key} es obligatorio")
            if not is_supported_precision(variant["precision"]):
                raise ValueError(f"Precisión no soportada en {profile['id']}.{role}: {variant['precision']}")
        profile_ids.add(profile["id"])


def select_profiles(config: dict, *, target: str | None = None, profile_id: str | None = None) -> list[dict]:
    profiles = config["profiles"]
    if profile_id is not None:
        selected = [profile for profile in profiles if profile["id"] == profile_id]
        if not selected:
            raise ValueError(f"Perfil desconocido: {profile_id}")
        return selected
    if target is not None:
        selected = [profile for profile in profiles if profile["target"] == target]
        if not selected:
            raise ValueError(f"Target desconocido: {target}")
        return selected
    return profiles


def config_digest(path: str | Path) -> str:
    source = Path(path)
    return hashlib.sha256(source.read_bytes()).hexdigest()
