"""Explicit, read-only parsing of the original QSettings INI format."""

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import TypeAdapter, ValidationError
from PySide6.QtCore import QSettings

from adapters.documents import Preferences, PresetDocument, ProjectDefaultsDocument
from adapters.storage import Settings
from domain.messages import QT_TRANSLATE_NOOP, Message
from domain.model import Box, default_presets

_BOX = TypeAdapter(tuple[int, int, int, int])
_SYSTEM_FIELDS = {
    "AdbPath": "adb_path",
    "RecentPath": "recent_projects",
    "Compression": "compression",
    "FaceMode": "face_mode",
    "Serial": "serial",
    "Server": "server",
    "Package": "package_name",
}


@dataclass(frozen=True)
class LegacyIssue:
    key: str
    message: str | Message


@dataclass
class LegacyPreview:
    source: Path
    repository: Path
    preferences: dict[str, object] = field(default_factory=dict)
    projects: dict[str, ProjectDefaultsDocument] = field(default_factory=dict)
    issues: list[LegacyIssue] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)

    @property
    def setting_count(self) -> int:
        return len(self.preferences)

    @property
    def preset_count(self) -> int:
        return sum(len(project.presets) for project in self.projects.values())

    @property
    def extension_count(self) -> int:
        return sum(len(project.extensions) for project in self.projects.values())


def _literal(value: object) -> object:
    return ast.literal_eval(value) if isinstance(value, str) else value


def _preset(value: object, kind: str) -> PresetDocument:
    try:
        data = _literal(value)
    except ValueError, SyntaxError:
        # Some early versions wrote IconPreset(...) reprs instead of dictionaries.
        # Inspect the call's literal keyword values; never evaluate or call it.
        text = str(value).strip()
        if text.startswith("<IconPreset ") and text.endswith(">"):
            body = re.sub(r",?\s+(?=(?:size|pivot|scale|angle)\s*=)", ", ", text[12:-1])
            text = f"IconPreset({body})"
        node = ast.parse(text, mode="eval").body
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            raise ValueError(
                Message(
                    QT_TRANSLATE_NOOP("Messages", "Expected a preset dictionary or IconPreset(...) format")
                )
            ) from None
        if node.func.id != "IconPreset" or node.args:
            raise ValueError(
                Message(QT_TRANSLATE_NOOP("Messages", "Expected IconPreset(...) with named arguments only"))
            )
        data = {keyword.arg: ast.literal_eval(keyword.value) for keyword in node.keywords}
    if not isinstance(data, dict) or not data or set(data) - {"size", "pivot", "scale", "angle"}:
        raise ValueError(
            Message(
                QT_TRANSLATE_NOOP("Messages", "Icon presets accept only size, pivot, scale and angle fields")
            )
        )
    return PresetDocument.model_validate({**vars(default_presets()[kind]), **data})


def _path(value: str, repository: Path) -> str:
    path = Path(value).expanduser()
    return str((repository / path).resolve())


def _setting(name: str, value: object, repository: Path) -> tuple[str, object]:
    key = _SYSTEM_FIELDS[name]
    if name == "AdbPath":
        value = str(value).strip()
        if not value:
            raise ValueError(Message(QT_TRANSLATE_NOOP("Messages", "The ADB executable path is empty")))
        # Bare commands retain PATH lookup; relative executable paths use the old working directory.
        if "/" in value or "\\" in value or Path(value).suffix:
            value = _path(value, repository)
    elif name == "RecentPath":
        value = [_path(str(value), repository)] if value else []
    elif name in {"FaceMode", "Compression"}:
        value = str(value).lower()
    elif name == "Server":
        value = str(value).upper()
    validated = Preferences.model_validate({key: value})
    return key, getattr(validated, key)


def preview_legacy(path: Path, repository: Path) -> LegacyPreview:
    """Parse without touching either settings file. Relative paths use ``repository``."""
    path, repository = Path(path).resolve(), Path(repository).resolve()
    if not path.is_file():
        raise FileNotFoundError(
            Message(QT_TRANSLATE_NOOP("Messages", "Legacy settings file not found: {0}"), (path,))
        )
    settings = QSettings(str(path), QSettings.Format.IniFormat)
    settings.setFallbacksEnabled(False)
    keys = settings.allKeys()
    if settings.status() != QSettings.Status.NoError:
        raise ValueError(
            Message(QT_TRANSLATE_NOOP("Messages", "Cannot read the legacy INI; check its file format"))
        )
    report = LegacyPreview(path, repository)
    kinds = default_presets()
    for key in keys:
        group, separator, name = key.partition("/")
        if not separator or group == "system" and name not in _SYSTEM_FIELDS:
            report.ignored.append(key)
            continue
        value = settings.value(key)
        try:
            if group == "system":
                field_name, parsed = _setting(name, value, repository)
                report.preferences[field_name] = parsed
            else:
                stem = group.removesuffix("_ex").removesuffix("_n").lower()
                project = report.projects.get(stem, ProjectDefaultsDocument())
                if name in kinds:
                    project.presets[name] = _preset(value, name)
                else:
                    extension: Box = _BOX.validate_python(_literal(value))
                    project.extensions[name] = extension
                report.projects[stem] = project
        except (ValueError, SyntaxError, TypeError) as error:
            if isinstance(error, ValidationError):
                message = "; ".join(item["msg"] for item in error.errors(include_input=False))
            elif error.args and isinstance(error.args[0], Message):
                message = error.args[0]
            else:
                message = str(error)
            report.issues.append(LegacyIssue(key, message))
    return report


def apply_legacy(preview: LegacyPreview, settings: Settings) -> None:
    """Merge the reviewed valid entries; preserve unrelated next preferences and defaults."""
    projects = {key: value.model_copy(deep=True) for key, value in settings.data.project_defaults.items()}
    for stem, imported in preview.projects.items():
        target = projects.setdefault(stem, ProjectDefaultsDocument())
        target.presets.update(imported.presets)
        target.extensions.update(imported.extensions)
    settings.update({**preview.preferences, "project_defaults": projects})
