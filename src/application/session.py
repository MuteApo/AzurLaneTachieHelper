import logging
import os
import shutil
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, replace
from hashlib import file_digest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Self

from PIL import Image

from adapters.documents import OptionsDocument, Preferences, PresetDocument, ProjectDocument
from adapters.storage import atomic_write, unique_path
from adapters.unity.index import discover_manifest
from adapters.unity.reader import UnityReader
from domain.imaging import align_image, clip_icon, display_layer, prepare_replacement, read_image, upright
from domain.imaging import composite as render_composite
from domain.messages import QT_TRANSLATE_NOOP, Message, Progress, no_progress
from domain.model import EditOptions, FaceMode, IconPreset, ImageAlignment, Kind, Project, default_presets

logger = logging.getLogger(__name__)


@dataclass
class ImportImage:
    key: str
    source: Path
    snapshot: Path
    size: tuple[int, int]
    canvas_size: tuple[int, int]
    preview: Image.Image | None = None
    reference: Image.Image | None = None


class MissingSourceError(FileNotFoundError):
    def __init__(self, path: Path, role: str | Message):
        self.path = path
        self.role = role
        super().__init__(
            Message(
                QT_TRANSLATE_NOOP("Messages", "Cannot find {0}: {1}. Select the file's new location."),
                (
                    role,
                    path,
                ),
            )
        )


@dataclass
class _State:
    sources: dict[str, Path]
    snapshots: dict[str, Path]
    options: EditOptions
    presets: dict[str, IconPreset]


@dataclass
class _Change:
    label: Message
    before: _State
    after: _State


class Session:
    """Own an editable project. Mutations are serialized by the caller.

    History references immutable compressed files on disk, never full pixel buffers.
    A state is committed only after all affected replacements have been prepared.
    """

    def __init__(self, project: Project):
        self.project = project
        self.path: Path | None = None
        self.manifest: Path | None = discover_manifest(project.metadata)
        presets = default_presets()
        for asset in project.assets:
            if asset.kind == Kind.ICON and asset.key in presets:
                presets[asset.key] = replace(presets[asset.key], size=asset.original.size)
        self._temporary = TemporaryDirectory(prefix="tachie-session-")
        self._state = _State({}, {}, deepcopy(project.options), presets)
        self._saved = deepcopy(self._state)
        self._exported = deepcopy(self._state)
        self._history: list[_Change] = []
        self._position = 0
        self._needs_save = False
        self.revision = 0
        self._images: OrderedDict[tuple, Image.Image] = OrderedDict()
        self._image_bytes = 0
        self._cache_limit = 128 * 1024 * 1024

    @classmethod
    def open(
        cls,
        path: Path,
        manifest: Path | None = None,
        progress: Progress = no_progress,
        relocations: dict[str, Path] | None = None,
        defaults: Preferences | None = None,
    ) -> Self:
        path = Path(path).resolve()
        if not path.name.lower().endswith(".json"):
            session = cls(UnityReader().load(path, manifest, progress))
            session.manifest = manifest or discover_manifest(path)
            if defaults is not None:
                session.apply_defaults(defaults)
            return session
        document = ProjectDocument.model_validate_json(path.read_text(encoding="utf-8"))

        def locate(value: str, role: str | Message) -> Path:
            source = (path.parent / value).resolve()
            source = Path((relocations or {}).get(str(source), source)).resolve()
            if not source.is_file():
                raise MissingSourceError(source, role)
            return source

        metadata = locate(document.metadata, Message(QT_TRANSLATE_NOOP("Messages", "Original assets")))
        source_manifest = manifest or (
            locate(document.manifest, Message(QT_TRANSLATE_NOOP("Messages", "Dependency index")))
            if document.manifest
            else None
        )
        session = cls(UnityReader().load(metadata, source_manifest, progress))
        session.manifest = source_manifest
        sources = {
            key: locate(value, Message(QT_TRANSLATE_NOOP("Messages", "replacement image {0}"), (key,)))
            for key, value in document.sources.items()
        }
        state = _State(
            sources,
            {key: session._capture(source) for key, source in sources.items()},
            EditOptions(**document.options.model_dump()),
            {
                **session.presets,
                **{key: IconPreset(**preset.model_dump()) for key, preset in document.presets.items()},
            },
        )
        session._apply(state)
        session.path = path
        session._saved = deepcopy(state)
        session._needs_save = bool(relocations)
        # Reopening restores edits, but does not assert that external output still exists.
        return session

    @property
    def dirty(self) -> bool:
        return self._needs_save or self._state != self._saved

    @property
    def export_dirty(self) -> bool:
        return bool(self.project.modified) and self._state != self._exported

    @property
    def can_undo(self) -> bool:
        return self._position > 0

    @property
    def can_redo(self) -> bool:
        return self._position < len(self._history)

    @property
    def undo_label(self) -> str | Message:
        return self._history[self._position - 1].label if self.can_undo else ""

    @property
    def redo_label(self) -> str | Message:
        return self._history[self._position].label if self.can_redo else ""

    @property
    def presets(self) -> dict[str, IconPreset]:
        return dict(self._state.presets)

    @property
    def sources(self) -> dict[str, Path]:
        return dict(self._state.sources)

    def apply_defaults(self, defaults: Preferences) -> None:
        """Initialize a newly opened metadata project; saved documents keep their own settings."""
        if self.path is not None or self._history:
            raise ValueError(
                Message(
                    QT_TRANSLATE_NOOP(
                        "Messages",
                        "Defaults apply only to newly opened original resources; they cannot replace existing edits",
                    )
                )
            )
        state = deepcopy(self._state)
        state.options.face_mode = defaults.face_mode
        state.options.compression = defaults.compression
        project_defaults = defaults.project_defaults.get(self.project.stem)
        if project_defaults is not None:
            state.options.extensions.update(project_defaults.extensions)
            state.presets.update(
                {kind: IconPreset(**preset.model_dump()) for kind, preset in project_defaults.presets.items()}
            )
        self._apply(state)
        self._saved = deepcopy(state)
        self._exported = deepcopy(state)

    def close(self):
        """Release session-owned snapshots after its background work has finished."""
        self._images.clear()
        self._image_bytes = 0
        self._temporary.cleanup()

    def _capture(self, source: Path) -> Path:
        """Keep the exact imported file even when an external editor overwrites it."""
        with source.open("rb") as incoming:
            digest = file_digest(incoming, "sha256").hexdigest()
            snapshot = Path(self._temporary.name) / f"{digest}{source.suffix.lower()}"
            if not snapshot.exists():
                incoming.seek(0)
                atomic_write(snapshot, lambda output: shutil.copyfileobj(incoming, output))
        return snapshot

    def _read(self, path: Path) -> Image.Image:
        stat = path.stat()
        key = str(path), stat.st_mtime_ns, stat.st_size
        if key in self._images:
            self._images.move_to_end(key)
            return self._images[key]
        image = read_image(path)
        weight = image.width * image.height * 4
        while self._images and self._image_bytes + weight > self._cache_limit:
            _, removed = self._images.popitem(last=False)
            self._image_bytes -= removed.width * removed.height * 4
        if weight <= self._cache_limit:
            self._images[key] = image
            self._image_bytes += weight
        return image

    def _apply(self, state: _State):
        target = replace(self.project, options=state.options)
        staged = {}
        previous = self._state.options
        for key, path in state.snapshots.items():
            asset = self.project.asset(key)
            extension_key = "paintingface" if asset.kind == Kind.FACE else key
            same_geometry = asset.kind == Kind.ICON or (
                state.options.face_mode == previous.face_mode
                and (
                    state.options.face_mode != FaceMode.CUSTOM
                    or state.options.extensions.get(extension_key, (0, 0, 0, 0))
                    == previous.extensions.get(extension_key, (0, 0, 0, 0))
                )
            )
            if self._state.snapshots.get(key) == path and same_geometry and asset.modified:
                staged[key] = asset.replacement, asset.replacement_box
                continue
            image = self._read(path)
            replacement, box = prepare_replacement(target, asset, image)
            staged[key] = replacement, box
        self.project.options = deepcopy(state.options)
        for asset in self.project.assets:
            asset.source = None
            asset.replacement, asset.replacement_box = staged.get(asset.key, (None, None))
        self._state = deepcopy(state)
        self.revision += 1

    def _commit(self, label: Message, state: _State):
        if state == self._state:
            return
        before = self._state
        self._apply(state)
        del self._history[self._position :]
        self._history.append(_Change(label, before, self._state))
        if len(self._history) > 100:
            self._history.pop(0)
        self._position = len(self._history)
        logger.info("%s · %s", label, self.project.name)

    def import_images(self, mapping: dict[str, Path]):
        state = deepcopy(self._state)
        for key, path in mapping.items():
            source = Path(path).resolve()
            state.sources[key] = source
            state.snapshots[key] = self._capture(source)
        self._commit(Message(QT_TRANSLATE_NOOP("Messages", "import {0} images"), (len(mapping),)), state)

    def prepare_imports(self, mapping: dict[str, Path]) -> list[ImportImage]:
        """Snapshot inputs before interaction; create bounded previews in the worker."""
        result = []
        artwork_reference = None
        for key, source in mapping.items():
            source = Path(source).resolve()
            snapshot = self._capture(source)
            image = self._read(snapshot)
            asset = self.project.asset(key)
            size = asset.original.size if asset.kind == Kind.ICON else self.project.size
            item = ImportImage(key, source, snapshot, image.size, size)
            if image.size != size:
                item.preview = upright(image)
                item.preview.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
                if asset.kind == Kind.ICON:
                    item.reference = self.preview(key)
                else:
                    if artwork_reference is None:
                        artwork_reference = self.preview(composite=True)
                        artwork_reference.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
                    item.reference = artwork_reference
            result.append(item)
        return result

    def import_prepared(self, items: list[ImportImage], alignments: dict[str, ImageAlignment]):
        state = deepcopy(self._state)
        for item in items:
            snapshot = item.snapshot
            if item.key in alignments:
                image = align_image(self._read(snapshot), item.canvas_size, alignments[item.key])
                temporary = Path(self._temporary.name) / "aligned.png"
                atomic_write(temporary, lambda output: upright(image).save(output, "PNG"))
                snapshot = self._capture(temporary)
            state.sources[item.key] = item.source
            state.snapshots[item.key] = snapshot
        self._commit(Message(QT_TRANSLATE_NOOP("Messages", "import {0} images"), (len(items),)), state)

    def match_images(self, paths: list[Path]) -> dict[Path, list[str]]:
        aliases: dict[str, set[str]] = {}
        for asset in self.project.assets:
            names = {asset.name, asset.key, asset.key.rsplit("/", 1)[-1]}
            if asset.texture_name:
                names.update({asset.texture_name, f"{asset.name} [{asset.texture_name}]"})
            if asset.kind == Kind.FACE:
                names.add(f"face #{asset.name}")
            aliases[asset.key] = {name.casefold() for name in names}
        result = {}
        for path in paths:
            stem = Path(path).stem.casefold()
            result[Path(path)] = [key for key, names in aliases.items() if stem in names]
        return result

    def reset(self, key: str):
        state = deepcopy(self._state)
        state.sources.pop(key, None)
        state.snapshots.pop(key, None)
        self._commit(Message(QT_TRANSLATE_NOOP("Messages", "reset image")), state)

    def set_options(self, *, face_mode=None, compression=None, extensions=None):
        state = deepcopy(self._state)
        if face_mode is not None:
            state.options.face_mode = face_mode
        if compression is not None:
            state.options.compression = compression
        if extensions is not None:
            state.options.extensions.update(extensions)
        self._commit(Message(QT_TRANSLATE_NOOP("Messages", "change processing options")), state)

    def set_presets(self, presets: dict[str, IconPreset]):
        state = deepcopy(self._state)
        state.presets.update(presets)
        self._commit(Message(QT_TRANSLATE_NOOP("Messages", "change portrait presets")), state)

    def undo(self):
        if self.can_undo:
            self._apply(self._history[self._position - 1].before)
            self._position -= 1

    def redo(self):
        if self.can_redo:
            self._apply(self._history[self._position].after)
            self._position += 1

    def save(self, path: Path) -> Path:
        path = Path(path).resolve()

        def relative(source: Path) -> str:
            try:
                return Path(os.path.relpath(source, path.parent)).as_posix()
            except ValueError:  # Different Windows drive: retain an absolute reference.
                return source.as_posix()

        assets = path.with_suffix(".assets")
        saved_sources = {}
        for key, snapshot in self._state.snapshots.items():
            destination = assets / snapshot.name
            if not destination.exists():
                with snapshot.open("rb") as incoming:
                    atomic_write(destination, lambda output: shutil.copyfileobj(incoming, output))
            saved_sources[key] = relative(destination)

        document = ProjectDocument(
            metadata=relative(self.project.metadata),
            manifest=relative(self.manifest) if self.manifest else None,
            sources=saved_sources,
            options=OptionsDocument(**vars(self._state.options)),
            presets={key: PresetDocument(**vars(value)) for key, value in self.presets.items()},
        )
        data = document.model_dump_json(indent=2).encode("utf-8")
        atomic_write(path, lambda stream: stream.write(data))
        self.path = path
        self._saved = deepcopy(self._state)
        self._needs_save = False
        logger.info("项目已保存：%s", path)
        return path

    def mark_exported(self):
        self._exported = deepcopy(self._state)

    def export_unity(self, destination: Path, progress: Progress = no_progress) -> list[Path]:
        from adapters.unity.writer import UnityWriter

        result = UnityWriter().export(self.snapshot(), destination, progress)
        self.mark_exported()
        return result

    def export_psd(self, path: Path, progress: Progress = no_progress) -> Path:
        from adapters.psd import export_psd

        return export_psd(self.snapshot(), path, progress)

    def snapshot(self) -> Project:
        """Images are immutable by convention; snapshot copies only mutable project metadata."""
        return replace(
            self.project,
            options=deepcopy(self.project.options),
            assets=[replace(asset) for asset in self.project.assets],
        )

    def preview(self, key: str | None = None, original=False, composite=False) -> Image.Image:
        project = self.project
        if original:
            project = replace(
                project, assets=[replace(a, replacement=None, replacement_box=None) for a in project.assets]
            )
        if composite or key is None:
            face_key = key if key and project.asset(key).kind == Kind.FACE else None
            image = render_composite(project, face_key)
        else:
            asset = project.asset(key)
            image = asset.image() if asset.kind == Kind.ICON else display_layer(project, asset)[0]
        return upright(image)

    def prepare_icon(self, reference: Path) -> tuple[Image.Image, tuple[float, float]]:
        preferred = self.project.preferred().placement
        if preferred is None:
            raise ValueError(
                Message(
                    QT_TRANSLATE_NOOP(
                        "Messages", "This project has no artwork suitable for portrait positioning."
                    )
                )
            )
        box = preferred.box(self.project.bias)
        image = self._read(Path(reference).resolve()).crop(box)
        face = self.project.face
        if face:
            face_box = face.box(self.project.bias)
            center = (face_box[0] + face_box[2]) / 2 - box[0], (face_box[1] + face_box[3]) / 2 - box[1]
        else:
            center = image.width / 2, image.height / 2
        return image, center

    def clip_icons(
        self, reference: Path, presets: dict[str, IconPreset], output: Path | None = None
    ) -> list[Path]:
        image, center = self.prepare_icon(reference)
        save_files = output is not None
        destination = unique_path(
            Path(output) / f"{self.project.stem}-icons"
            if output is not None
            else Path(self._temporary.name) / "portraits"
        )
        # Generate all pixels first; invalid parameters never change the edit session.
        images = {
            kind: clip_icon(image, center, preset, kind == "shipyardicon") for kind, preset in presets.items()
        }
        files = []
        state = deepcopy(self._state)
        for kind, clipped in images.items():
            path = destination / f"{kind}.png"
            atomic_write(path, lambda stream, img=clipped: upright(img).save(stream, format="PNG"))
            if save_files:
                files.append(path)
            if any(a.key == kind for a in self.project.assets):
                state.sources[kind] = path.resolve()
                state.snapshots[kind] = self._capture(path)
        state.presets.update(presets)
        self._commit(Message(QT_TRANSLATE_NOOP("Messages", "crop portraits")), state)
        return files
