"""Compatibilidad de la serialización de eventos movida a `events.py`."""

from vision_core.core.serialization.events import event_to_json_dict, event_to_payload

__all__ = ["event_to_json_dict", "event_to_payload"]
