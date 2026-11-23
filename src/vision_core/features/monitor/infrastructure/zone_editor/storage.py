"""Escritura atómica del JSON de zonas con restauración ante fallos."""

import os
import tempfile
from collections.abc import Callable
from pathlib import Path

from vision_core.core.errors import ZoneConfigurationError

ReplaceFunction = Callable[[Path, Path], None]


def read_zone_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise ZoneConfigurationError(f"no se puede leer el archivo de zonas '{path}': {error}") from None


def restore_zone_bytes(path: Path, original: bytes | None, *, replace: ReplaceFunction = os.replace) -> None:
    """Restaura el contenido previo, o elimina el archivo si no existía."""
    if original is None:
        path.unlink(missing_ok=True)
        return
    write_zone_bytes(path, original, replace=replace)


def write_zone_bytes(path: Path, payload: bytes, *, replace: ReplaceFunction = os.replace) -> None:
    """Escribe en temporal y sustituye el archivo; si falla, deja el original.

    ``replace`` es inyectable para verificar la restauración del archivo ante
    errores de escritura simulados en los tests.
    """
    parent = path.parent
    original = path.read_bytes() if path.is_file() else None
    backup_path: Path | None = None
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=parent, prefix=".zones-backup-", delete=False) as backup:
            backup_path = Path(backup.name)
            if original is not None:
                backup.write(original)
                backup.flush()
                os.fsync(backup.fileno())

        with tempfile.NamedTemporaryFile(dir=parent, prefix=".zones-new-", delete=False) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())

        replace(temporary_path, path)
    except BaseException:
        try:
            if original is not None and backup_path is not None:
                replace(backup_path, path)
            elif original is None:
                path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    finally:
        for leftover in (temporary_path, backup_path):
            if leftover is not None:
                leftover.unlink(missing_ok=True)
