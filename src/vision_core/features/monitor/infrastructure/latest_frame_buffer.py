"""Thread-safe size-one buffer with a strict "drop old" policy.

The inference thread is the producer. ``publish`` only swaps one reference
while holding the lock for a few instructions; it never waits for rendering,
JPEG encoding or any downstream I/O. The consumer takes the newest payload
and leaves the slot empty, so intermediate frames are discarded instead of
building an unbounded queue.
"""

import threading
from typing import Generic, TypeVar

T = TypeVar("T")


class LatestFrameBuffer(Generic[T]):
    """Buffer de tamaño 1: el productor nunca se bloquea esperando al consumidor."""

    __slots__ = ("_dropped", "_item", "_lock", "_published")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._item: T | None = None
        self._published = 0
        self._dropped = 0

    def publish(self, item: T) -> bool:
        """Sobrescribe el frame anterior y devuelve si descartó uno.

        Nunca llama al consumidor ni espera por él.
        """
        with self._lock:
            replaced = self._item is not None
            if replaced:
                self._dropped += 1
            self._item = item
            self._published += 1
            return replaced

    def take(self) -> T | None:
        """Devuelve (y retira) el payload más reciente, o ``None`` si no hay uno."""
        with self._lock:
            item, self._item = self._item, None
            return item

    def peek(self) -> T | None:
        """Consulta el payload actual sin retirarlo."""
        with self._lock:
            return self._item

    def clear(self) -> None:
        with self._lock:
            self._item = None

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "published": self._published,
                "dropped": self._dropped,
                "queued": 1 if self._item is not None else 0,
            }
