"""Versioned JSON at the persistence boundary; pixel data stays in image files."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

from domain.model import FaceMode

PositiveInt = Annotated[int, Field(gt=0)]
PositiveFloat = Annotated[FiniteFloat, Field(gt=0)]


class OptionsDocument(BaseModel):
    face_mode: FaceMode = FaceMode.OFF
    compression: Literal["original", "lz4", "none"] = "original"
    extensions: dict[str, tuple[int, int, int, int]] = Field(default_factory=dict)


class PresetDocument(BaseModel):
    size: tuple[PositiveInt, PositiveInt]
    pivot: tuple[FiniteFloat, FiniteFloat] = (0.5, 0.6)
    scale: PositiveFloat = 0.6
    angle: FiniteFloat = 0.0


class ProjectDocument(BaseModel):
    version: Literal[1] = 1
    metadata: str
    manifest: str | None = None
    sources: dict[str, str] = Field(default_factory=dict)
    options: OptionsDocument = Field(default_factory=OptionsDocument)
    presets: dict[str, PresetDocument] = Field(default_factory=dict)


class ProjectDefaultsDocument(BaseModel):
    presets: dict[str, PresetDocument] = Field(default_factory=dict)
    extensions: dict[str, tuple[int, int, int, int]] = Field(default_factory=dict)


class Preferences(BaseModel):
    # Future UI preferences can survive an older app opening the same file.
    model_config = ConfigDict(extra="allow")
    recent_projects: list[str] = Field(default_factory=list)
    manifest_path: str = ""
    pull_directory: str = ""
    adb_path: str = "adb"
    serial: str = "auto"
    server: Literal["CN", "JP", "EN"] = "CN"
    package_name: str = ""
    compression: Literal["original", "lz4", "none"] = "original"
    language: Literal["system", "zh_CN", "en"] = "system"
    face_mode: FaceMode = FaceMode.OFF
    project_defaults: dict[str, ProjectDefaultsDocument] = Field(default_factory=dict)
