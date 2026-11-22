"""Bounded thread-safe buffer with a strict "drop old" policy.

The inference thread is the producer. ``publish`` only updates a small deque
while holding the lock for a few instructions; it never waits for rendering,
JPEG encoding or any downstream I/O. The consumer takes the oldest queued
payload, so intermediate frames are discarded instead of building an unbounded
queue.
"""

import threading
from collections import deque
from typing import Generic, TypeVar

T = TypeVar("T")


class LatestFrameBuffer(Generic[T]):
    """Buffer de tamaño 1: el productor nunca se bloquea."""

    __slots__ = ("_dropped", "_items", "_lock", "_maxsize", "_published")

    def __init__(self, maxsize: int = 1) -> None:
        if maxsize != 1:
            raise ValueError("maxsize debe ser 1")
        self._lock = threading.Lock()
        self._maxsize = maxsize
        self._items: deque[T] = deque(maxlen=maxsize)
        self._published = 0
        self._dropped = 0

    @property
    def maxsize(self) -> int:
        return self._maxsize

    def publish(self, item: T) -> bool:
        """Añade el frame más reciente y devuelve si descartó uno viejo."""
        with self._lock:
            dropped = len(self._items) == self._maxsize
            if dropped:
                self._dropped += 1
            self._items.append(item)
            self._published += 1
            return dropped

    def take(self) -> T | None:
        """Devuelve (y retira) el payload más antiguo, o ``None`` si no hay uno."""
        with self._lock:
            return self._items.popleft() if self._items else None

    def peek(self) -> T | None:
        """Consulta el payload más reciente sin retirarlo."""
        with self._lock:
            return self._items[-1] if self._items else None

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "published": self._published,
                "dropped": self._dropped,
                "queued": len(self._items),
            }
