from typing import Any, Protocol


class EmbeddingExtractor(Protocol):
    def __call__(self, crop: Any) -> Any: ...
