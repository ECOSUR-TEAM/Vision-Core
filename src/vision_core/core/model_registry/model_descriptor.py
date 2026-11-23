from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelDescriptor:
    id: str
    name: str
    task: str
    version: str
    artifact_version: str
    selector: str
    source: str
    source_url: str | None
    license: str
    license_url: str | None
    license_notes: str | None
    registered_at: str
    checksum_algorithm: str
    checksum_value: str | None
    expected_config: dict[str, object]
    model_card: str
    status: str

    @property
    def model_hash(self) -> str:
        if self.checksum_value is None:
            return "unverified"
        return f"{self.checksum_algorithm}:{self.checksum_value}"
