from typing import Any

import yaml

from vision_core.shared.errors import ConfigurationError


class UniqueKeySafeLoader(yaml.SafeLoader):
    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        mapping: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                raise ConfigurationError(f"clave duplicada en el registro de modelos: {key}")
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping
