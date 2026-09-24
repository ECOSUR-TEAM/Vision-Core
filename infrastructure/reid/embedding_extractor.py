from collections.abc import Callable

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

class TorchvisionEmbeddingExtractor:
    """Extracts embeddings from images using a Torchvision model."""

    def __init__(
            self, 
            model_name : str = "mobilenet_v3_small",
            device : str | None = None,

    ) -> None:
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        if model_name == "resnet50":
            weights = ResNet50_Weights.DEFAULT
            model = resnet50(weights=weights)
            self._model = nn.Sequential(
                *list(model.children())[:-1],
            )
            self._transform = weights.transforms()
        elif model_name == "mobilenet_v3_small":
            weights = MobileNet_V3_Small_Weights.DEFAULT
            model = mobilenet_v3_small(weights=weights)
            self._model = nn.Sequential(
                model.features,
                model.avgpool,
                nn.Flatten(),
            )
            self._transform = weights.transforms()
        else:
            raise ValueError(f"Unknown model name: {model_name}")

        self._model.eval().to(self.device)


    def __call__(self, crop: np.ndarray) -> np.ndarray:
        if crop.size == 0:
            raise ValueError("El recorte de la persona está vacío")

        if crop.ndim != 3 or crop.shape[2] != 3:
            raise ValueError("El recorte debe tener forma HxWx3")

        # OpenCV entrega BGR; los pesos de torchvision esperan RGB.
        crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)

        tensor = self._transform(Image.fromarray(crop_rgb))
        tensor = tensor.unsqueeze(0).to(self.device)

        with torch.inference_mode():
            embedding = self._model(tensor)
            embedding = torch.nn.functional.normalize(embedding, p=2, dim=1)

        return embedding.squeeze(0).cpu().numpy().astype(np.float32)

