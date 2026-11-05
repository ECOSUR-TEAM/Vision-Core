"""Session identity memory with a small appearance gallery per person."""
import math
import os
import time
import uuid
from collections import deque

import numpy as np
from domain.entities import BBox

from domain.ports import ReIDMemory

TTL_SECONDS = 60
SIMILARITY_THRESHOLD = 0.85


class InMemoryReID(ReIDMemory):
    """Recover absent people; never match an identity assigned to a visible track.

    ttl_seconds=0 retains identities until this memory instance is discarded.
    The constructor retains the legacy 60-second default for existing callers;
    application entry points use from_env(), which defaults to the whole session.
    """

    def __init__(self, *, ttl_seconds=TTL_SECONDS, similarity_threshold=SIMILARITY_THRESHOLD,
                 ambiguity_margin=0.03, gallery_size=8) -> None:
        if not math.isfinite(ttl_seconds) or ttl_seconds < 0:
            raise ValueError('El tiempo de memoria debe ser finito y no negativo')
        if not 0 < similarity_threshold <= 1 or not 0 <= ambiguity_margin <= 1:
            raise ValueError('Umbrales de similitud inválidos')
        if type(gallery_size) is not int or gallery_size < 1:
            raise ValueError('El tamaño de la galería debe ser positivo')
        self.ttl_seconds = ttl_seconds
        self.threshold = similarity_threshold
        self.margin = ambiguity_margin
        self.gallery_size = gallery_size
        self._active: dict[int, str] = {}
        self._lost: dict[str, tuple[np.ndarray, float]] = {}
        self._gallery: dict[str, deque] = {}
        self._retired_tracks: dict[int, str] = {}
        self._reserved: set[str] = set()

    def begin_frame(self, visible_track_ids: set[int]) -> None:
        self._reserved = {self._retired_tracks[t] for t in visible_track_ids
                          if t in self._retired_tracks}

    @classmethod
    def from_env(cls):
        return cls(ttl_seconds=float(os.getenv('VISION_CORE_REID_TTL_SECONDS', '0')),
                   similarity_threshold=float(os.getenv('VISION_CORE_REID_THRESHOLD', '0.85')))

    def _purge(self, now):
        if self.ttl_seconds == 0:
            return
        for person, (_, lost_at) in list(self._lost.items()):
            if now - lost_at >= self.ttl_seconds:
                del self._lost[person]
                self._gallery.pop(person, None)
                self._retired_tracks = {t: p for t, p in self._retired_tracks.items() if p != person}

    @staticmethod
    def _normalize(embedding):
        value = np.asarray(embedding, dtype=np.float32)
        if value.ndim != 1 or not np.isfinite(value).all() or np.linalg.norm(value) < 1e-12:
            raise ValueError('Embedding inválido')
        return value / np.linalg.norm(value)

    def _remember(self, person, vector):
        gallery = self._gallery.setdefault(person, deque(maxlen=self.gallery_size))
        # Keep different views instead of filling the gallery with identical frames.
        if not gallery or max(float(np.dot(v, vector)) for v in gallery) < .98:
            gallery.append(vector.copy())

    def resolve(self, track_id: int, embedding: np.ndarray, bbox: BBox) -> str:
        self._purge(time.monotonic())
        vector = self._normalize(embedding)
        if track_id in self._active:
            person = self._active[track_id]
            self._remember(person, vector)
            return person

        # The motion tracker may retain its ID across a short occlusion. Prefer
        # that association over guessing between similar-looking absent people.
        retained = self._retired_tracks.get(track_id)
        if retained in self._lost:
            person = retained
            del self._lost[person]
            self._retired_tracks = {t: p for t, p in self._retired_tracks.items() if p != person}
            self._active[track_id] = person
            self._remember(person, vector)
            return person

        candidates = []
        for person, (last, _) in self._lost.items():
            if person in self._reserved:
                continue
            views = list(self._gallery.get(person, ())) + [last]
            score = max(float(np.dot(v, vector)) for v in views)
            candidates.append((score, person))
        candidates.sort(reverse=True)
        best = candidates[0] if candidates else None
        unambiguous = len(candidates) < 2 or candidates[0][0] - candidates[1][0] >= self.margin
        if best and best[0] > self.threshold and unambiguous:
            person = best[1]
            del self._lost[person]
        else:
            person = str(uuid.uuid4())
        self._active[track_id] = person
        self._retired_tracks = {t: p for t, p in self._retired_tracks.items() if p != person}
        self._remember(person, vector)
        return person

    def mark_lost(self, person_id: str, embedding: np.ndarray) -> None:
        now = time.monotonic()
        self._purge(now)
        vector = self._normalize(embedding)
        self._retired_tracks.update({track: person for track, person in self._active.items()
                                     if person == person_id})
        self._active = {track: person for track, person in self._active.items()
                        if person != person_id}
        self._remember(person_id, vector)
        # Duplicate notifications must not extend the retention window.
        if person_id not in self._lost:
            self._lost[person_id] = (vector.copy(), now)
