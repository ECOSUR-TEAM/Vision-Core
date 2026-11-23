import hashlib
from pathlib import Path

CHECKSUM_CHUNK_BYTES = 1024 * 1024


def compute_file_checksum(path: str | Path, algorithm: str = "sha256") -> str:
    digest = hashlib.new(algorithm)
    source = Path(path)
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHECKSUM_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()
