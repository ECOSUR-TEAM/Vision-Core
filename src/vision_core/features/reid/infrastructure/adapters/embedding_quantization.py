from collections.abc import Sequence

import cv2
import numpy as np
import torch
from PIL import Image
from torch import nn

from vision_core.core.errors import ConfigurationError

CALIBRATION_SEED = 20261120
CALIBRATION_SAMPLES = 8


def calibration_tensors(transform, crops: Sequence[np.ndarray]) -> list[torch.Tensor]:
    tensors = []
    for crop in crops:
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        tensors.append(transform(Image.fromarray(rgb)).unsqueeze(0).to("cpu"))
    if not tensors:
        raise ConfigurationError("La calibración INT8 requiere al menos un recorte de persona.")
    return tensors


def synthetic_calibration_crops(size: int = 128) -> list[np.ndarray]:
    generator = np.random.default_rng(CALIBRATION_SEED)
    crops = []
    for _ in range(CALIBRATION_SAMPLES):
        noise = generator.integers(0, 256, size=(size, size, 3), dtype=np.uint8)
        crop = np.ascontiguousarray(noise)
        cv2.rectangle(crop, (20, 20), (size - 20, size - 20), (235, 235, 235), thickness=-1)
        crops.append(crop)
    return crops


def quantize_embedding_model(
    model: nn.Module,
    transform,
    crops: Sequence[np.ndarray],
) -> nn.Module:
    try:
        from torch.ao.quantization import get_default_qconfig_mapping
        from torch.ao.quantization.quantize_fx import convert_fx, prepare_fx
    except ImportError as error:
        raise ConfigurationError(
            "La cuantización INT8 requiere torch.ao.quantization; actualiza PyTorch CPU.",
            context={"variable": "VISION_CORE_EMBEDDING_PRECISION"},
        ) from error

    example_inputs = calibration_tensors(transform, crops)
    try:
        prepared = prepare_fx(
            model.eval(),
            get_default_qconfig_mapping("x86"),
            example_inputs=(example_inputs[0],),
        )
        with torch.inference_mode():
            for tensor in example_inputs:
                prepared(tensor)
        quantized = convert_fx(prepared)
    except Exception as error:
        raise ConfigurationError(
            f"No se pudo cuantizar el extractor de embeddings: {error}",
            context={"variable": "VISION_CORE_EMBEDDING_PRECISION"},
        ) from error
    return quantized.eval()
