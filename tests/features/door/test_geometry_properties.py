import tempfile
from pathlib import Path

from vision_core.features.door.infrastructure.config.zone_loader import load_zones
from vision_core.shared.errors import ZoneConfigurationError


def test_load_zones_rejects_invalid_json():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "zones.json"
        p.write_text("{invalid")
        try:
            load_zones(p)
        except ZoneConfigurationError:
            return
        raise AssertionError("expected ZoneConfigurationError")
