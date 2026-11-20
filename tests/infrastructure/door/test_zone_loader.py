import json
import re
from pathlib import Path

import pytest

from vision_core.features.door.infrastructure.adapters.polygon_door_analytics import PolygonDoorAnalytics
from vision_core.features.door.infrastructure.config.zone_loader import load_zones as load_zones_feature
from vision_core.features.door.infrastructure.config.zone_schema import (
    MAX_CONFIG_FILE_BYTES,
    MAX_ZONE_POINTS,
    REQUIRED_KEYS,
)
from vision_core.infrastructure.door.zone_config import ZoneConfig
from vision_core.infrastructure.door.zone_loader import load_zones
from vision_core.shared.errors import ZoneConfigurationError

EXAMPLE = Path(__file__).resolve().parents[3] / "config" / "zones.example.json"
LOADERS = (load_zones, load_zones_feature)
LOADER_IDS = ("legacy", "feature")


def _example_data():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def _write(tmp_path, data):
    path = tmp_path / "zones.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.mark.parametrize("loader", LOADERS, ids=LOADER_IDS)
def test_load_zones_builds_configuration(loader):
    zones = loader(EXAMPLE)

    assert isinstance(zones, ZoneConfig)
    assert (zones.width, zones.height) == (640, 480)
    assert zones.door.name == "door"
    assert zones.exterior.name == "exterior"
    assert zones.interior.name == "interior"


@pytest.mark.parametrize("loader", LOADERS, ids=LOADER_IDS)
def test_shared_edge_prefers_interior(loader):
    zones = loader(EXAMPLE)
    analytics = PolygonDoorAnalytics(zones.exterior, zones.interior, zones.door, confirmation_frames=1)
    assert analytics._zone_for((320, 200)) == "interior"
    assert analytics._point_in_polygon((320, 200), zones.door)


@pytest.mark.parametrize("loader", LOADERS, ids=LOADER_IDS)
def test_configuration_bounds(loader, tmp_path):
    data = _example_data()
    data["frame_size"] = [300, 480]
    with pytest.raises(ValueError, match="fuera"):
        loader(_write(tmp_path, data))


@pytest.mark.parametrize("loader", LOADERS, ids=LOADER_IDS)
def test_valid_document_loads(loader):
    zones = loader(EXAMPLE)

    assert (zones.width, zones.height) == (640, 480)
    assert len(zones.door.points) == 4
    assert len(zones.exterior.points) == 4
    assert len(zones.interior.points) == 4


@pytest.mark.parametrize("loader", LOADERS, ids=LOADER_IDS)
def test_float_frame_size_is_rejected(loader, tmp_path):
    data = _example_data()
    data["frame_size"] = [640.0, 480.0]

    with pytest.raises(ZoneConfigurationError, match="entero positivo"):
        loader(_write(tmp_path, data))


@pytest.mark.parametrize("loader", LOADERS, ids=LOADER_IDS)
def test_file_size_limit_is_enforced(loader, tmp_path):
    path = tmp_path / "big.json"
    path.write_text(" " * (MAX_CONFIG_FILE_BYTES + 1), encoding="utf-8")

    with pytest.raises(ZoneConfigurationError, match="supera el límite"):
        loader(path)


@pytest.mark.parametrize("loader", LOADERS, ids=LOADER_IDS)
def test_malformed_json_is_rejected(loader, tmp_path):
    path = tmp_path / "broken.json"
    path.write_text('{"version": "1.0",', encoding="utf-8")

    with pytest.raises(ZoneConfigurationError, match="JSON malformado"):
        loader(path)


@pytest.mark.parametrize("loader", LOADERS, ids=LOADER_IDS)
def test_duplicate_json_keys_are_rejected(loader, tmp_path):
    path = tmp_path / "duplicated.json"
    path.write_text('{"version": "1.0", "version": "1.0"}', encoding="utf-8")

    with pytest.raises(ZoneConfigurationError, match="clave duplicada"):
        loader(path)


@pytest.mark.parametrize("loader", LOADERS, ids=LOADER_IDS)
def test_non_utf8_file_is_rejected(loader, tmp_path):
    path = tmp_path / "bad_encoding.json"
    path.write_bytes(b"\xff\xfe{}")

    with pytest.raises(ZoneConfigurationError, match="UTF-8"):
        loader(path)


@pytest.mark.parametrize("loader", LOADERS, ids=LOADER_IDS)
def test_missing_file_is_reported_cleanly(loader, tmp_path):
    with pytest.raises(ZoneConfigurationError, match="no se puede acceder al archivo de zonas"):
        loader(tmp_path / "inexistente.json")


@pytest.mark.parametrize("loader", LOADERS, ids=LOADER_IDS)
def test_top_level_must_be_an_object(loader, tmp_path):
    with pytest.raises(ZoneConfigurationError, match="debe ser un objeto JSON"):
        loader(_write(tmp_path, []))


@pytest.mark.parametrize("loader", LOADERS, ids=LOADER_IDS)
@pytest.mark.parametrize("key", REQUIRED_KEYS)
def test_missing_required_key_is_rejected(loader, key, tmp_path):
    data = _example_data()
    del data[key]

    with pytest.raises(ZoneConfigurationError, match=rf"faltan claves requeridas.*{key}"):
        loader(_write(tmp_path, data))


@pytest.mark.parametrize("loader", LOADERS, ids=LOADER_IDS)
@pytest.mark.parametrize("key", ["_note", "extra"])
def test_unknown_key_is_rejected(loader, key, tmp_path):
    data = _example_data()
    data[key] = "no permitido"

    with pytest.raises(ZoneConfigurationError, match=rf"claves desconocidas no permitidas.*{key}"):
        loader(_write(tmp_path, data))


@pytest.mark.parametrize("loader", LOADERS, ids=LOADER_IDS)
@pytest.mark.parametrize("version", ["2.0", 1, None, True])
def test_invalid_schema_version_is_rejected(loader, version, tmp_path):
    data = _example_data()
    data["version"] = version

    with pytest.raises(ZoneConfigurationError, match="version:"):
        loader(_write(tmp_path, data))


@pytest.mark.parametrize("loader", LOADERS, ids=LOADER_IDS)
@pytest.mark.parametrize(
    ("value", "message"),
    [
        ([True, 720], "frame_size[0]: se esperaba un entero positivo"),
        ([640, False], "frame_size[1]: se esperaba un entero positivo"),
        ([640, "480"], "frame_size[1]: se esperaba un entero positivo"),
        ([640], "frame_size: debe ser una lista o tupla de exactamente 2 enteros positivos"),
        ([640, 480, 1], "frame_size: debe ser una lista o tupla de exactamente 2 enteros positivos"),
        ("640x480", "frame_size: debe ser una lista o tupla de exactamente 2 enteros positivos"),
        ([640, -1], "frame_size[1]: se esperaba un entero positivo"),
        ([float("nan"), 480], "frame_size[0]: se esperaba un entero positivo"),
        ([float("inf"), 480], "frame_size[0]: se esperaba un entero positivo"),
    ],
)
def test_invalid_frame_size_is_rejected(loader, value, message, tmp_path):
    data = _example_data()
    data["frame_size"] = value

    with pytest.raises(ZoneConfigurationError, match=re.escape(message)):
        loader(_write(tmp_path, data))


@pytest.mark.parametrize("loader", LOADERS, ids=LOADER_IDS)
def test_boolean_coordinate_is_rejected(loader, tmp_path):
    data = _example_data()
    data["door"][0][0] = True

    with pytest.raises(ZoneConfigurationError, match=re.escape("door[0][0]: se esperaba un número real finito")):
        loader(_write(tmp_path, data))


@pytest.mark.parametrize("loader", LOADERS, ids=LOADER_IDS)
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), "320", None])
def test_non_finite_or_non_numeric_coordinate_is_rejected(loader, value, tmp_path):
    data = _example_data()
    data["exterior"][0][0] = value

    with pytest.raises(ZoneConfigurationError, match=re.escape("exterior[0][0]")):
        loader(_write(tmp_path, data))


@pytest.mark.parametrize("loader", LOADERS, ids=LOADER_IDS)
@pytest.mark.parametrize("point", [[1], [1, 2, 3], "1,2"])
def test_malformed_coordinate_is_rejected(loader, point, tmp_path):
    data = _example_data()
    data["door"][0] = point

    with pytest.raises(ZoneConfigurationError, match=re.escape("cada coordenada debe ser")):
        loader(_write(tmp_path, data))


@pytest.mark.parametrize("loader", LOADERS, ids=LOADER_IDS)
def test_too_many_points_is_rejected(loader, tmp_path):
    data = _example_data()
    data["interior"] = [[index % 640, index // 640] for index in range(MAX_ZONE_POINTS + 1)]

    with pytest.raises(ZoneConfigurationError, match=rf"supera el máximo de {MAX_ZONE_POINTS} puntos"):
        loader(_write(tmp_path, data))


@pytest.mark.parametrize("loader", LOADERS, ids=LOADER_IDS)
def test_geometry_errors_are_reported_with_the_field_name(loader, tmp_path):
    data = _example_data()
    data["door"] = [[300, 100], [300, 100], [350, 120], [350, 420]]

    with pytest.raises(ZoneConfigurationError, match="door: Vértices repetidos"):
        loader(_write(tmp_path, data))
