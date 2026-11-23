"""Validación compartida del esquema 1.0: única fuente de verdad para HTTP y loader."""

import json

import pytest

from vision_core.core.errors import ZoneConfigurationError, codes
from vision_core.core.validation.zone_payload import (
    MAX_ZONE_PAYLOAD_BYTES,
    MAX_ZONE_POINTS,
    reject_duplicate_json_keys,
    validate_zone_payload,
    validate_zone_schema,
)

EXAMPLE = {
    "version": "1.0",
    "frame_size": [640, 480],
    "door": [[290, 120], [350, 120], [350, 420], [290, 420]],
    "exterior": [[0, 0], [320, 0], [320, 479], [0, 479]],
    "interior": [[320, 0], [639, 0], [639, 479], [320, 479]],
}


def _copy(**overrides):
    return {**EXAMPLE, **overrides}


def test_valid_document_is_normalized():
    document = validate_zone_payload(_copy())

    assert document["frame_size"] == (640, 480)
    assert document["door"][0] == (290.0, 120.0)
    assert validate_zone_schema(_copy()) == document


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda data: data.update(version="2.0"), "version:"),
        (lambda data: data.update(frame_size=[640.0, 480]), "entero positivo"),
        (lambda data: data.update(frame_size=[640, 0]), "entero positivo"),
        (lambda data: data.update(extra="<script>"), "claves desconocidas"),
        (lambda data: data.pop("interior"), "faltan claves requeridas"),
        (lambda data: data.update(door=[[1, 1], [2, 2]]), "al menos 3 puntos"),
        (lambda data: data.update(door=[[300, 100], [300, 100], [350, 120], [350, 420]]), "Vértices repetidos"),
        (lambda data: data.update(door=[[300, 100], [500, 400], [350, 120], [350, 420]]), "cruza consigo mismo"),
        (lambda data: data.update(door=[[0, 0], [640, 0], [0, 10]]), "vértices fuera de la imagen"),
    ],
)
def test_invalid_documents_fail_with_zone_error(mutator, message):
    data = _copy()
    mutator(data)

    with pytest.raises(ZoneConfigurationError, match=message) as error:
        validate_zone_payload(data)

    assert error.value.code in (codes.ZONE_CONFIG_INVALID, codes.ZONE_GEOMETRY_INVALID)


def test_payload_size_is_bounded_before_schema():
    huge = _copy(door=[[1, 1], [2, 2], [3, 3]])

    with pytest.raises(ZoneConfigurationError, match="supera el límite"):
        validate_zone_payload(huge, max_bytes=10)
    assert MAX_ZONE_PAYLOAD_BYTES == 100 * 1024


def test_duplicate_keys_are_rejected():
    with pytest.raises(ZoneConfigurationError, match="clave duplicada"):
        json.loads('{"version":"1.0","version":"1.0"}', object_pairs_hook=reject_duplicate_json_keys)


def test_xss_payload_in_zone_name_is_not_a_valid_document():
    data = _copy()
    data["<script>alert(1)</script>"] = []

    with pytest.raises(ZoneConfigurationError, match="claves desconocidas"):
        validate_zone_payload(data)


def test_more_than_max_points_is_rejected():
    data = _copy(interior=[[index % 640, index // 640] for index in range(MAX_ZONE_POINTS + 1)])

    with pytest.raises(ZoneConfigurationError, match="supera el máximo"):
        validate_zone_payload(data)
