from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetentionResult:
    events: int = 0
    zone_observations: int = 0
    tracks: int = 0
    identities: int = 0
    persons: int = 0
    sessions: int = 0
    metrics: int = 0

    @property
    def total(self) -> int:
        return (
            self.events
            + self.zone_observations
            + self.tracks
            + self.identities
            + self.persons
            + self.sessions
            + self.metrics
        )
