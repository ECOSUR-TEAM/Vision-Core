from vision_core.core.errors import ConfigurationError
from vision_core.core.model_registry.model_descriptor import ModelDescriptor


class ModelRegistry:
    def __init__(self, models: tuple[ModelDescriptor, ...]) -> None:
        self._models = models
        self._by_id = {model.id: model for model in models}

    def all(self) -> tuple[ModelDescriptor, ...]:
        return self._models

    def get(self, model_id: str) -> ModelDescriptor:
        try:
            return self._by_id[model_id]
        except KeyError:
            available = ", ".join(sorted(self._by_id)) or "ninguno"
            raise ConfigurationError(
                f"model_id desconocido '{model_id}'. Modelos registrados: {available}.",
                context={"variable": "MODEL_ID"},
            ) from None

    def resolve(self, model_id: str, *, task: str, selector: str) -> ModelDescriptor:
        model = self.get(model_id)
        if model.task != task:
            raise ConfigurationError(
                f"El modelo '{model_id}' es de tipo '{model.task}', pero se solicitó uno de tipo '{task}'.",
                context={"variable": "MODEL_ID"},
            )
        if model.status != "active":
            raise ConfigurationError(
                f"El modelo '{model_id}' tiene estado '{model.status}' y no puede usarse en arranques normales.",
                context={"variable": "MODEL_ID"},
            )
        if model.selector != selector:
            raise ConfigurationError(
                f"El modelo '{model_id}' espera el selector '{model.selector}', "
                f"pero la configuración usa '{selector}'.",
                context={"variable": "MODEL_ID"},
            )
        return model
