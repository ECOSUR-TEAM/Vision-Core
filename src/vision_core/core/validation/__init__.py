"""Validación de formato compartida por los mappers de aplicación (ADR 0008)."""

from vision_core.core.validation.validation import (
    bounded_int,
    finite_bbox,
    finite_float,
    finite_unit_float,
    immutable_json_value,
    json_metadata,
    required_str,
    required_track_id,
    validate_frame,
)

__all__ = [
    "bounded_int",
    "finite_bbox",
    "finite_float",
    "finite_unit_float",
    "immutable_json_value",
    "json_metadata",
    "required_str",
    "required_track_id",
    "validate_frame",
]
