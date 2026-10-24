"""Device download operations and index caching, independent of the dialog."""

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

from adapters.adb import AdbClient, PullResult
from adapters.unity.index import dependency_index
from domain.messages import QT_TRANSLATE_NOOP, Message, Progress, no_progress


def resource_names(path: Path) -> list[str]:
    """Offer base paintings; alternate bundles are pulled automatically."""
    return sorted(
        (
            key.removeprefix("painting/")
            for key in dependency_index(path)
            if key.startswith("painting/") and not key.endswith(("_tex", "_n", "_hx"))
        ),
        key=str.casefold,
    )


def index_cache(root: Path, package: str, serial: str) -> Path:
    key = hashlib.sha256(f"{package}:{serial}".encode()).hexdigest()[:16]
    return root / "resource-indices" / key / "dependencies"


def refresh_index(
    client: AdbClient, target: Path, progress: Progress = no_progress
) -> tuple[Path, list[str]]:
    progress(Message(QT_TRANSLATE_NOOP("Messages", "Pulling dependency index")), 0, 0)
    client.connect()
    target.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=target.parent, prefix=".index-") as temporary:
        downloaded = client.pull_dependencies(Path(temporary))
        names = resource_names(downloaded)
        downloaded.replace(target)
    return target, names


def pull_resources(
    client: AdbClient, name: str, destination: Path, progress: Progress = no_progress
) -> tuple[PullResult, Path, list[str]]:
    progress(Message(QT_TRANSLATE_NOOP("Messages", "Connecting to device")), 0, 0)
    client.connect()
    progress(Message(QT_TRANSLATE_NOOP("Messages", "Reading dependency index")), 0, 0)
    index_file = client.pull_dependencies(destination)
    result = client.pull_project(name, dependency_index(index_file), destination, progress)
    return result, index_file, resource_names(index_file)


def can_open(result: PullResult) -> bool:
    optional = {"paintingface", "shipyardicon", "herohrzicon", "squareicon"}
    return result.metadata is not None and all(name.split("/", 1)[0] in optional for name in result.failed)
