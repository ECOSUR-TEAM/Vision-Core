import os

import numpy as np
import cv2
import torch
from PIL import Image
from torch import nn
from torchvision.models import (
    MobileNet_V3_Small_Weights,
    ResNet50_Weights,
    mobilenet_v3_small,
    resnet50,
)


class TorchvisionEmbeddingExtractor:
    """Extrae embeddings visuales de un recorte de persona usando un modelo
    preentrenado de torchvision. Los pesos se descargan si no están en caché."""

    def __init__(self, model_name: str = "mobilenet_v3_small", device: str | None = None) -> None:
        if model_name not in {"resnet50", "mobilenet_v3_small"}:
            raise ValueError(f"Unknown model name: {model_name}")
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        if self.device.type not in {"cpu", "cuda"}:
            raise ValueError("El dispositivo debe ser cpu o cuda")
        if self.device.type == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("Se solicitó CUDA, pero no está disponible")
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
            raise ValueError(f"Unknown model name: {model_name}")

        self._model.eval().to(self.device)

    @classmethod
    def from_env(cls):
        return cls(os.getenv("VISION_CORE_EMBEDDING_MODEL", "mobilenet_v3_small"),
                   os.getenv("VISION_CORE_EMBEDDING_DEVICE") or None)

    def __call__(self, crop: np.ndarray) -> np.ndarray:
        if not isinstance(crop, np.ndarray) or crop.dtype != np.uint8:
            raise ValueError("El recorte debe ser un ndarray BGR uint8")
        if crop.size == 0:
            raise ValueError("El recorte de la persona está vacío")
        if crop.ndim != 3 or crop.shape[2] != 3:
            raise ValueError("El recorte debe tener forma HxWx3")

        crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        tensor = self._transform(Image.fromarray(crop_rgb)).unsqueeze(0).to(self.device)

        with torch.inference_mode():
            embedding = self._model(tensor).flatten(start_dim=1)
            norm = torch.linalg.vector_norm(embedding, dim=1)
            if not torch.isfinite(embedding).all() or not torch.all(norm > 1e-12):
                raise ValueError("El modelo produjo un embedding no finito o de norma cero")
            embedding = torch.nn.functional.normalize(embedding, p=2, dim=1)

        return embedding.squeeze(0).cpu().numpy().astype(np.float32)
