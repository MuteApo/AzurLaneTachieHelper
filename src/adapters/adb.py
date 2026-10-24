"""Explicit device access and selected AssetBundle extraction; no import-time I/O."""

import logging
import re
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import adbutils
from adbutils.errors import AdbError

from domain.messages import QT_TRANSLATE_NOOP, Message, Progress

logger = logging.getLogger(__name__)
PACKAGES = {
    "CN": "com.bilibili.azurlane",
    "JP": "com.YoStarJP.AzurLane",
    "EN": "com.YoStarEN.AzurLane",
}
EMULATOR_ENDPOINTS = (
    "127.0.0.1:5555",
    "127.0.0.1:7555",
    "127.0.0.1:16384",
    "127.0.0.1:21503",
    "127.0.0.1:59865",
    "127.0.0.1:62001",
)


@dataclass
class PullResult:
    metadata: Path | None
    files: list[Path]
    failed: list[str]


def _asset_path(value: str) -> PurePosixPath:
    """Manifest paths must remain relative to the AssetBundles directory."""
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or ".." in path.parts
        or not path.parts
        or any(character in value for character in '\\:*?"<>|\x00')
    ):
        raise ValueError(Message(QT_TRANSLATE_NOOP("Messages", "Invalid resource path: {0!r}"), (value,)))
    return path


class AdbClient:
    def __init__(
        self,
        executable: Path | str = "adb",
        serial: str = "auto",
        package: str = PACKAGES["CN"],
        apk_fallback: bool = True,
    ):
        if not re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+", package):
            raise ValueError(Message(QT_TRANSLATE_NOOP("Messages", "Enter a valid Android package name")))
        self.executable = str(executable)
        self.serial = serial
        self.package = package
        self.apk_fallback = apk_fallback
        self._connected = False
        self._client: adbutils.AdbClient | None = None

    def _server(self) -> adbutils.AdbClient:
        if self._client is None:
            client = adbutils.AdbClient(socket_timeout=30)
            if self.executable not in ("", "adb"):
                # adbutils speaks to the server directly. A custom binary only
                # needs to start that server; do not mutate process-wide settings.
                completed = subprocess.run(
                    [self.executable, "-H", client.host, "-P", str(client.port), "start-server"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if completed.returncode:
                    raise AdbError(completed.stderr.strip() or completed.stdout.strip())
            self._client = client
        return self._client

    def _call[T](self, operation: str, function: Callable[[], T]) -> T:
        try:
            return function()
        except AdbError as error:
            raise RuntimeError(
                Message(
                    QT_TRANSLATE_NOOP("Messages", "ADB {0} failed: {1}"),
                    (operation, str(error)),
                )
            ) from error

    def devices(self) -> list[str]:
        return self._call(
            "devices", lambda: [item.serial for item in self._server().list() if item.state == "device"]
        )

    def connect(self, serial: str | None = None) -> str:
        requested = self.serial if serial is None else serial
        self._connected = False
        ready = self.devices()
        if requested == "auto":
            if not ready:
                for endpoint in EMULATOR_ENDPOINTS:
                    try:
                        self._server().connect(endpoint, timeout=5)
                    except AdbError:
                        continue
                    ready = self.devices()
                    if ready:
                        break
            if not ready:
                raise RuntimeError(
                    Message(
                        QT_TRANSLATE_NOOP(
                            "Messages",
                            "No device is available; start the emulator or connect a device and authorize USB debugging",
                        )
                    )
                )
            requested = ready[0]
        elif requested not in ready:
            if ":" in requested:
                self._call("connect", lambda: self._server().connect(requested, timeout=15))
                ready = self.devices()
            if requested not in ready:
                raise RuntimeError(
                    Message(
                        QT_TRANSLATE_NOOP(
                            "Messages",
                            "Device {0} is unavailable; check its connection and debugging authorization",
                        ),
                        (requested,),
                    )
                )
        self.serial = requested
        self._connected = True
        logger.info("已选择设备 %s", requested)
        return requested

    def _device(self) -> adbutils.AdbDevice:
        if not self._connected:
            self.connect()
        return self._server().device(serial=self.serial)

    def _pull_file(self, remote: str, output: Path) -> None:
        # FileSync streams to disk and inherits the client's 30-second socket
        # inactivity timeout; large APKs can continue while data keeps arriving.
        self._call("pull", lambda: self._device().sync.pull_file(remote, output))

    def pull_dependencies(self, destination: Path) -> Path:
        result = self._pull_assets(["dependencies"], destination, {})
        if result.failed:
            raise RuntimeError(
                Message(
                    QT_TRANSLATE_NOOP(
                        "Messages",
                        "Cannot pull dependencies; check that game resources have been downloaded. See the log for details.",
                    )
                )
            )
        return result.files[0]

    def pull_project(
        self,
        name: str,
        index: Mapping[str, Sequence[str]],
        destination: Path,
        progress: Progress | None = None,
    ) -> PullResult:
        if len(_asset_path(name).parts) != 1:
            raise ValueError(
                Message(QT_TRANSLATE_NOOP("Messages", "The painting name cannot contain a directory"))
            )
        primary = f"painting/{name}"
        if primary not in index:
            raise ValueError(
                Message(
                    QT_TRANSLATE_NOOP(
                        "Messages", "{0} is missing from the index; check the name or update dependencies"
                    ),
                    (primary,),
                )
            )
        roots = [primary]
        variant = f"painting/{name}_n"
        if variant in index:
            roots.append(variant)
        # Walk dependency references once, including shared/nested dependencies.
        assets: list[str] = []
        visited: set[str] = set()

        def include(asset: str) -> None:
            if asset in visited:
                return
            visited.add(asset)
            assets.append(asset)
            for dependency in index.get(asset, ()):
                include(dependency)

        for root in roots:
            include(root)
        include(f"paintingface/{name}")
        for kind in ("shipyardicon", "herohrzicon", "squareicon"):
            include(f"{kind}/{name}")
        renamed = {root: PurePosixPath(root).name for root in roots}
        result = self._pull_assets(assets, destination, renamed, progress)
        metadata = destination.resolve() / name
        result.metadata = metadata if metadata in result.files else None
        return result

    def _pull_assets(
        self,
        assets: list[str],
        destination: Path,
        renamed: dict[str, str],
        progress: Progress | None = None,
    ) -> PullResult:
        paths = {asset: Path(*_asset_path(renamed.get(asset, asset)).parts) for asset in assets}
        for asset in assets:
            _asset_path(asset)
        destination = destination.resolve()
        for relative in paths.values():
            target = destination / relative
            if not target.resolve().is_relative_to(destination):
                raise ValueError(
                    Message(
                        QT_TRANSLATE_NOOP(
                            "Messages", "The output path is outside the destination folder: {0}"
                        ),
                        (relative,),
                    )
                )
            if target.exists():
                raise FileExistsError(
                    Message(
                        QT_TRANSLATE_NOOP(
                            "Messages", "The destination exists; choose a new download folder: {0}"
                        ),
                        (target,),
                    )
                )
        if not self._connected:
            self.connect()
        destination.mkdir(parents=True, exist_ok=True)
        failed: list[str] = []
        files: list[Path] = []
        with TemporaryDirectory(prefix=".pull-", dir=destination) as temporary:
            stage = Path(temporary)
            for current, asset in enumerate(assets, 1):
                if progress:
                    progress(
                        Message(QT_TRANSLATE_NOOP("Messages", "Pulling {0}"), (asset,)),
                        current - 1,
                        len(assets),
                    )
                output = stage / paths[asset]
                output.parent.mkdir(parents=True, exist_ok=True)
                remote = f"/sdcard/Android/data/{self.package}/files/AssetBundles/{asset}"
                try:
                    self._pull_file(remote, output)
                except RuntimeError as error:
                    logger.warning("%s：%s", asset, error)
                    output.unlink(missing_ok=True)
                    failed.append(asset)
            if failed and self.apk_fallback:
                if progress:
                    progress(
                        Message(
                            QT_TRANSLATE_NOOP("Messages", "Looking for missing resources in installed APKs")
                        ),
                        len(assets),
                        len(assets),
                    )
                self._recover_from_apks(failed, paths, stage)
            if progress:
                progress(
                    Message(QT_TRANSLATE_NOOP("Messages", "Organizing downloaded resources")),
                    len(assets),
                    len(assets),
                )
            for asset in assets:
                if asset in failed:
                    continue
                source, target = stage / paths[asset], destination / paths[asset]
                target.parent.mkdir(parents=True, exist_ok=True)
                # Exclusive creation also protects files added after preflight.
                with source.open("rb") as incoming, target.open("xb") as outgoing:
                    try:
                        shutil.copyfileobj(incoming, outgoing)
                    except BaseException:
                        outgoing.close()
                        target.unlink()
                        raise
                files.append(target)
        logger.info("拉取完成：%s 个文件，%s 个缺失", len(files), len(failed))
        return PullResult(None, files, failed)

    def _recover_from_apks(self, failed: list[str], paths: dict[str, Path], stage: Path) -> None:
        try:
            result = self._call(
                "shell", lambda: self._device().shell2(["pm", "path", self.package], timeout=30)
            )
            if result.returncode:
                logger.warning("查询 %s 的 APK 失败：%s", self.package, result.output.strip())
                return
            apks = [
                line.removeprefix("package:").strip()
                for line in result.output.splitlines()
                if line.startswith("package:")
            ]
            if not apks:
                logger.warning("设备上没有找到 %s 的 APK", self.package)
            for number, remote in enumerate(apks):
                local = stage / f"fallback-{number}.apk"
                self._pull_file(remote, local)
                with ZipFile(local) as archive:
                    names = set(archive.namelist())
                    for asset in list(failed):
                        candidates = [f"assets/AssetBundles/{asset}"]
                        if asset.split("/", 1)[0] in {"shipyardicon", "herohrzicon", "squareicon"}:
                            candidates.append(candidates[0] + ".ys")
                        member = next((candidate for candidate in candidates if candidate in names), None)
                        if member is None:
                            continue
                        target = stage / paths[asset]
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(member) as incoming, target.open("wb") as outgoing:
                            shutil.copyfileobj(incoming, outgoing)
                        failed.remove(asset)
                local.unlink()
                if not failed:
                    break
        except RuntimeError as error:
            logger.warning("APK 资源回退失败：%s", error)
