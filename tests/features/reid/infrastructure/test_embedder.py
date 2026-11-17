from pathlib import Path

import numpy as np
import pytest
import torch
from torch import nn

from infrastructure.reid import embedder as module


@pytest.fixture
def extractor(monkeypatch):
    class Network(nn.Module):
        def __init__(self):
            super().__init__()
            self.features = nn.Identity()
            self.avgpool = nn.AdaptiveAvgPool2d(1)
    monkeypatch.setattr(module, 'mobilenet_v3_small', lambda **kwargs: Network())
    return module.TorchvisionEmbeddingExtractor(device='cpu')


def test_preprocessing_bgr_rgb_and_l2(extractor):
    crop = np.full((80, 40, 3), [10, 80, 240], dtype=np.uint8)
    output = extractor(crop)
    expected = (np.array([240, 80, 10]) / 255 - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
    expected /= np.linalg.norm(expected)
    np.testing.assert_allclose(output, expected, atol=1e-6)
    assert output.dtype == np.float32 and output.ndim == 1
    assert not extractor._model.training
    np.testing.assert_array_equal(output, extractor(crop))


@pytest.mark.parametrize('crop', [None, np.zeros((0, 3, 3), dtype=np.uint8),
    np.zeros((10, 10), dtype=np.uint8), np.zeros((10, 10, 4), dtype=np.uint8),
    np.zeros((10, 10, 3), dtype=np.float32)])
def test_invalid_crops(extractor, crop):
    with pytest.raises(ValueError):
        extractor(crop)


def test_resnet_output_flattened(monkeypatch):
    model = nn.Sequential(nn.AdaptiveAvgPool2d(1), nn.Identity())
    monkeypatch.setattr(module, 'resnet50', lambda **kwargs: model)
    extractor = module.TorchvisionEmbeddingExtractor('resnet50', 'cpu')
    assert extractor(np.zeros((30, 20, 3), dtype=np.uint8)).shape == (3,)


@pytest.mark.parametrize('value', [0.0, float('nan'), float('inf')])
def test_invalid_embeddings_rejected(extractor, value):
    class Invalid(nn.Module):
        def forward(self, tensor):
            return torch.full((1, 5), value)
    extractor._model = Invalid()
    with pytest.raises(ValueError):
        extractor(np.zeros((30, 20, 3), dtype=np.uint8))


def test_unavailable_cuda_fails_before_loading(monkeypatch):
    monkeypatch.setattr(torch.cuda, 'is_available', lambda: False)
    with pytest.raises(RuntimeError, match='CUDA'):
        module.TorchvisionEmbeddingExtractor(device='cuda')


def test_unknown_model():
    with pytest.raises(ValueError):
        module.TorchvisionEmbeddingExtractor('unsupported')


@pytest.mark.parametrize('name,weights,dimension', [
    ('mobilenet_v3_small', module.MobileNet_V3_Small_Weights.DEFAULT, 576),
    ('resnet50', module.ResNet50_Weights.DEFAULT, 2048),
])
@pytest.mark.parametrize('device', ['cpu', 'cuda'])
def test_real_pretrained_model(name, weights, dimension, device):
    if device == 'cuda' and not torch.cuda.is_available():
        pytest.skip('CUDA no disponible')
    checkpoint = Path(torch.hub.get_dir()) / 'checkpoints' / weights.url.rsplit('/', 1)[-1]
    if not checkpoint.is_file():
        pytest.skip('Pesos preentrenados ausentes; las pruebas no descargan archivos')
    extractor = module.TorchvisionEmbeddingExtractor(name, device)
    crop = np.random.default_rng(42).integers(0, 256, (128, 64, 3), dtype=np.uint8)
    output = extractor(crop)
    assert output.shape == (dimension,)
    assert output.dtype == np.float32 and np.isfinite(output).all()
    assert np.linalg.norm(output) == pytest.approx(1, abs=1e-6)
    np.testing.assert_allclose(output, extractor(crop), atol=1e-6)
