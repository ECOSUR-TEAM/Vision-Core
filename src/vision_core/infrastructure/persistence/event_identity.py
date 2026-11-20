import hashlib
import json

from vision_core.features.pipeline.application.mappers.pipeline_mapper import event_to_dict
from vision_core.shared.domain.event import Event


def event_id_for(event: Event) -> str:
    explicit = getattr(event, "event_id", None)
    if explicit:
        return str(explicit)
    payload = json.dumps(event_to_dict(event), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
