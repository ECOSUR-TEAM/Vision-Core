from collections.abc import Sequence

import cv2
import numpy as np
import torch
from PIL import Image
from torch import nn
from torchvision.models import (
    MobileNet_V3_Small_Weights,
    ResNet50_Weights,
    mobilenet_v3_small,
    resnet50,
)

from vision_core.core.config import Settings
from vision_core.core.config.settings_precision import is_supported_precision
from vision_core.core.errors import (
    ConfigurationError,
    ReIDError,
    ReIDModelUnavailableError,
    ValidationError,
    codes,
)
from vision_core.features.reid.infrastructure.adapters.embedding_quantization import (
    quantize_embedding_model,
    synthetic_calibration_crops,
)
from vision_core.model_registry.model_descriptor import ModelDescriptor

SUPPORTED_BASE_MODELS = frozenset({"resnet50", "mobilenet_v3_small"})
PRECISION_SUFFIXES = {"-int8": "int8", "-fp16": "fp16"}


class TorchvisionEmbeddingExtractor:
    """Extrae embeddings visuales de un recorte de persona usando un modelo
    preentrenado de torchvision. Los pesos se descargan si no están en caché."""

    def __init__(
        self,
        model_name: str = "mobilenet_v3_small",
        device: str | None = None,
        model_descriptor: ModelDescriptor | None = None,
        precision: str = "fp32",
        calibration_crops: Sequence[np.ndarray] | None = None,
    ) -> None:
        base_model = model_name
        selector_precision = "fp32"
        for suffix, suffix_precision in PRECISION_SUFFIXES.items():
            if model_name.endswith(suffix):
                base_model = model_name[: -len(suffix)]
                selector_precision = suffix_precision
                break
        if base_model not in SUPPORTED_BASE_MODELS:
            raise ConfigurationError(
                "El modelo de embeddings configurado no es válido.",
                context={"variable": "VISION_CORE_EMBEDDING_MODEL"},
            )
        if not is_supported_precision(precision) or precision != selector_precision:
            raise ConfigurationError(
                f"La precisión '{precision}' no coincide con el modelo '{model_name}' ({selector_precision}).",
                context={"variable": "VISION_CORE_EMBEDDING_PRECISION"},
            )
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        if self.device.type not in {"cpu", "cuda"}:
            raise ConfigurationError("El dispositivo debe ser cpu o cuda")
        if self.device.type == "cuda" and not torch.cuda.is_available():
            raise ReIDModelUnavailableError("Se solicitó CUDA, pero no está disponible")
        if precision == "fp16" and self.device.type != "cuda":
            raise ConfigurationError(
                "La precisión fp16 de embeddings requiere CUDA.",
                context={"variable": "VISION_CORE_EMBEDDING_PRECISION"},
            )
        if precision == "int8" and self.device.type != "cpu":
            raise ConfigurationError(
                "La cuantización INT8 con backend x86 requiere CPU.",
                context={"variable": "VISION_CORE_EMBEDDING_PRECISION"},
            )
        self.model_name = model_name
        self.model_descriptor = model_descriptor
        self.precision = precision
        self._model: nn.Module

        if base_model == "resnet50":
            weights = ResNet50_Weights.DEFAULT
            model = resnet50(weights=weights)
            self._model = nn.Sequential(*list(model.children())[:-1])
            self._transform = weights.transforms()
        else:
            weights = MobileNet_V3_Small_Weights.DEFAULT
            model = mobilenet_v3_small(weights=weights)
            self._model = nn.Sequential(model.features, model.avgpool, nn.Flatten())
            self._transform = weights.transforms()

        self._model.eval().to(self.device)
        if precision == "fp16":
            self._model.half()
        elif precision == "int8":
            crops = synthetic_calibration_crops() if calibration_crops is None else calibration_crops
            self._model = quantize_embedding_model(self._model, self._transform, crops)

    @classmethod
    def from_env(cls, model_descriptor: ModelDescriptor | None = None):
        settings = Settings.from_env(validate_startup=False).reid
        return cls(
            settings.model_name,
            settings.device,
            model_descriptor,
            settings.precision,
        )

    def __call__(self, crop: np.ndarray) -> np.ndarray:
        if not isinstance(crop, np.ndarray) or crop.dtype != np.uint8:
            raise ValidationError("El recorte debe ser un ndarray BGR uint8", code=codes.REID_INPUT_INVALID)
        if crop.size == 0:
            raise ValidationError("El recorte de la persona está vacío", code=codes.REID_INPUT_INVALID)
        if crop.ndim != 3 or crop.shape[2] != 3:
            raise ValidationError("El recorte debe tener forma HxWx3", code=codes.REID_INPUT_INVALID)

        crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        tensor = self._transform(Image.fromarray(crop_rgb)).unsqueeze(0).to(self.device)
        if self.precision == "fp16":
            tensor = tensor.half()

        with torch.inference_mode():
            embedding = self._model(tensor).flatten(start_dim=1)
            norm = torch.linalg.vector_norm(embedding, dim=1)
            if not torch.isfinite(embedding).all() or not torch.all(norm > 1e-12):
                raise ReIDError("El modelo produjo un embedding no finito o de norma cero")
            embedding = torch.nn.functional.normalize(embedding, p=2, dim=1)

        # Única transferencia GPU -> CPU; el modelo ya produce float32, así que
        # np.asarray evita una copia adicional (antes: .astype(np.float32)).
        return np.asarray(embedding.squeeze(0).cpu().numpy(), dtype=np.float32)
