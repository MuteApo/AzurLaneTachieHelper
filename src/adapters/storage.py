import os
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import BinaryIO

from adapters.documents import Preferences


def atomic_write(path: Path, write: Callable[[BinaryIO], object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            write(stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return path


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    index = 2
    while (candidate := path.with_name(f"{path.stem}-{index}{path.suffix}")).exists():
        index += 1
    return candidate


class Settings:
    def __init__(self, path: Path):
        self.path = path
        self.data = (
            Preferences.model_validate_json(path.read_text(encoding="utf-8"))
            if path.exists()
            else Preferences()
        )

    def get(self, key: str, default=None):
        return getattr(self.data, key, default)

    def set(self, key: str, value):
        self.update({key: value})

    def update(self, values: Mapping[str, object]) -> None:
        """Validate and persist one preference change, including multi-field imports."""
        updated = Preferences.model_validate({**self.data.model_dump(), **values})
        encoded = updated.model_dump_json(indent=2).encode("utf-8")
        atomic_write(self.path, lambda stream: stream.write(encoded))
        self.data = updated
