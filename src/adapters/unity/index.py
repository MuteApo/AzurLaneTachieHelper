from functools import lru_cache
from pathlib import Path

import UnityPy
from UnityPy import config as unity_config
from UnityPy.enums import ClassIDType as ClassID

from domain.messages import QT_TRANSLATE_NOOP, Message


def safe_relative(value: str) -> Path:
    path = Path(value.replace("\\", "/"))
    if path.is_absolute() or path.drive or ".." in path.parts or ":" in value:
        raise ValueError(
            Message(
                QT_TRANSLATE_NOOP("Messages", "The resource path must be inside the project: {0}"), (value,)
            )
        )
    return path


@lru_cache(maxsize=4)
def _dependency_index(path: str, modified_ns: int) -> dict[str, tuple[str, ...]]:
    # Index discovery also runs before any project has been opened.
    unity_config.FALLBACK_UNITY_VERSION = "2022.3.62f3"
    env = UnityPy.load(path)
    for reader in env.objects:
        if reader.type == ClassID.MonoBehaviour:
            data = reader.parse_as_object()
            if hasattr(data, "m_Keys") and hasattr(data, "m_Values"):
                return {k: tuple(v.m_Dependencies) for k, v in zip(data.m_Keys, data.m_Values)}
    raise ValueError(
        Message(QT_TRANSLATE_NOOP("Messages", "The selected file is not a valid dependencies index."))
    )


def dependency_index(path: Path) -> dict[str, tuple[str, ...]]:
    return _dependency_index(str(path.resolve()), path.stat().st_mtime_ns)


def discover_manifest(metadata: Path) -> Path | None:
    return next((p / "dependencies" for p in metadata.parents if (p / "dependencies").is_file()), None)


def project_root(metadata: Path) -> Path:
    return metadata.parent.parent if metadata.parent.name == "painting" else metadata.parent
