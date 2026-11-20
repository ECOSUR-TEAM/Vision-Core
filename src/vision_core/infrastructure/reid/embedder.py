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

from vision_core.settings import Settings
from vision_core.shared.errors import (
    ConfigurationError,
    ReIDError,
    ReIDModelUnavailableError,
    ValidationError,
    codes,
)


class TorchvisionEmbeddingExtractor:
    """Extrae embeddings visuales de un recorte de persona usando un modelo
    preentrenado de torchvision. Los pesos se descargan si no están en caché."""

    def __init__(self, model_name: str = "mobilenet_v3_small", device: str | None = None) -> None:
        if model_name not in {"resnet50", "mobilenet_v3_small"}:
            raise ConfigurationError(
                "El modelo de embeddings configurado no es válido.",
                context={"variable": "VISION_CORE_EMBEDDING_MODEL"},
            )
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        if self.device.type not in {"cpu", "cuda"}:
            raise ConfigurationError("El dispositivo debe ser cpu o cuda")
        if self.device.type == "cuda" and not torch.cuda.is_available():
            raise ReIDModelUnavailableError("Se solicitó CUDA, pero no está disponible")
        self.model_name = model_name

        if model_name == "resnet50":
            weights = ResNet50_Weights.DEFAULT
            model = resnet50(weights=weights)
            self._model = nn.Sequential(*list(model.children())[:-1])
            self._transform = weights.transforms()
        elif model_name == "mobilenet_v3_small":
            weights = MobileNet_V3_Small_Weights.DEFAULT
            model = mobilenet_v3_small(weights=weights)
            self._model = nn.Sequential(model.features, model.avgpool, nn.Flatten())
            self._transform = weights.transforms()
        else:
            raise ConfigurationError("El modelo de embeddings configurado no es válido.")

        self._model.eval().to(self.device)

    @classmethod
    def from_env(cls):
        settings = Settings.from_env(validate_startup=False).reid
        return cls(
            settings.model_name,
            settings.device,
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

        with torch.inference_mode():
            embedding = self._model(tensor).flatten(start_dim=1)
            norm = torch.linalg.vector_norm(embedding, dim=1)
            if not torch.isfinite(embedding).all() or not torch.all(norm > 1e-12):
                raise ReIDError("El modelo produjo un embedding no finito o de norma cero")
            embedding = torch.nn.functional.normalize(embedding, p=2, dim=1)

        # Única transferencia GPU -> CPU; el modelo ya produce float32, así que
        # np.asarray evita una copia adicional (antes: .astype(np.float32)).
        return np.asarray(embedding.squeeze(0).cpu().numpy(), dtype=np.float32)
