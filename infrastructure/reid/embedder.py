import sys
from pathlib import Path

_TORCHREID = Path(__file__).resolve().parents[2] / "third_party" / "deep-person-reid"
if _TORCHREID.exists():
    sys.path.insert(0, str(_TORCHREID))

import numpy as np
import torch
from torchreid.utils import FeatureExtractor

EMBED_DIM = 512

_TORCHREID = Path(__file__).resolve().parents[2] / "third_party" / "deep-person-reid"
if _TORCHREID.exists():
    sys.path.insert(0, str(_TORCHREID))
    
class OsnetEmbedder:
    """Embedder ReID con OSNet (torchreid), salida L2-normalizada."""

    def __init__(
        self,
        model_name: str = "osnet_x1_0",
        model_path: str = "models/osnet_x1_0_market1501.pth",
        device: str | None = None,
    ) -> None:
        device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._extractor = FeatureExtractor(
            model_name=model_name,
            model_path=model_path,
            device=device,
        )

    def __call__(self, crop: np.ndarray) -> np.ndarray:
        if crop.size == 0:
            return np.zeros(EMBED_DIM, dtype=np.float32)
        # FeatureExtractor acepta ndarray BGR (h, w, c), redimensiona y normaliza solo
        feat = self._extractor([crop])[0]
        feat = torch.nn.functional.normalize(feat, dim=0)
        return feat.cpu().numpy()