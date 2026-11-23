"""Escritura atómica del JSON de zonas con restauración ante fallos."""

import os
import stat
import tempfile
from collections.abc import Callable
from pathlib import Path

from vision_core.core.errors import ZoneConfigurationError
from vision_core.core.validation.zone_payload import MAX_ZONE_PAYLOAD_BYTES

ReplaceFunction = Callable[[Path, Path], None]


def read_zone_bytes(path: Path, *, max_bytes: int = MAX_ZONE_PAYLOAD_BYTES) -> bytes:
    try:
        if path.is_file() and path.stat().st_size > max_bytes:
            raise ZoneConfigurationError(f"el archivo de zonas supera {max_bytes} bytes: {path}")
        data = path.read_bytes()
    except OSError as error:
        raise ZoneConfigurationError(f"no se puede leer el archivo de zonas '{path}': {error}") from None
    if len(data) > max_bytes:
        raise ZoneConfigurationError(f"el archivo de zonas supera {max_bytes} bytes: {path}")
    return data


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
    mode = stat.S_IMODE(path.stat().st_mode) if path.is_file() else None
    backup_path: Path | None = None
    backup_ready = False
    temporary_path: Path | None = None
    try:
        if original is not None:
            with tempfile.NamedTemporaryFile(dir=parent, prefix=".zones-backup-", delete=False) as backup:
                backup_path = Path(backup.name)
                backup.write(original)
                backup.flush()
                os.fsync(backup.fileno())
            backup_ready = True

        with tempfile.NamedTemporaryFile(dir=parent, prefix=".zones-new-", delete=False) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
            if mode is not None:
                os.chmod(temporary_path, mode)

        replace(temporary_path, path)
        temporary_path = None
    except BaseException:
        try:
            if original is not None and backup_ready and backup_path is not None:
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
