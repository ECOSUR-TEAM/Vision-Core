from dataclasses import dataclass

from vision_core.features.reid.domain.ports.embedding_extractor import EmbeddingExtractor
from vision_core.features.reid.domain.ports.reid_memory import ReIDMemory
from vision_core.features.reid.infrastructure.adapters.embedder import TorchvisionEmbeddingExtractor
from vision_core.features.reid.infrastructure.adapters.memory_reid import InMemoryReID


@dataclass(frozen=True)
class ReIDDependencies:
    memory: ReIDMemory
    embedder: EmbeddingExtractor


def build_reid(
    memory: ReIDMemory | None = None,
    embedder: EmbeddingExtractor | None = None,
) -> ReIDDependencies:
    if memory is None:
        memory = InMemoryReID.from_env()
    if embedder is None:
        embedder = TorchvisionEmbeddingExtractor.from_env()
    return ReIDDependencies(memory=memory, embedder=embedder)
