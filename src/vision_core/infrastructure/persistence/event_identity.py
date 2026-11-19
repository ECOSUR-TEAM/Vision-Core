import hashlib
import json

from vision_core.application.event_serializer import event_to_dict


def event_id_for(event: object) -> str:
    explicit = getattr(event, "event_id", None)
    if explicit:
        return str(explicit)
    payload = json.dumps(event_to_dict(event), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
