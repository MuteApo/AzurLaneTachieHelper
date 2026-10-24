from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path
from typing import cast

from PIL import Image

from domain.geometry import Affine
from domain.messages import QT_TRANSLATE_NOOP, Message

type Point = tuple[float, float]
type Box = tuple[int, int, int, int]


@dataclass(frozen=True)
class ImageAlignment:
    """Imported image's top-left position and uniform scale on its target canvas."""

    x: float = 0
    y: float = 0
    scale: float = 1


class FaceMode(StrEnum):
    OFF = "off"
    AUTO = "auto"
    CUSTOM = "custom"


class Kind(StrEnum):
    PAINTING = "painting"
    FACE = "paintingface"
    ICON = "icon"


@dataclass(frozen=True)
class ObjectRef:
    bundle: Path
    cabinet: str
    path_id: int


@dataclass(frozen=True)
class Placement:
    """Rect in prefab space: bottom-left origin, scaled edge lengths and unit axes.

    Axes retain rotation, reflection and shear from the parent Transform chain.
    The prefab root's external scene transform is intentionally factored out.
    """

    origin: Point
    size: Point
    pivot: Point = (0.5, 0.5)
    anchored: Point = (0.0, 0.0)
    scale: Point = (1.0, 1.0)
    rect: ObjectRef | None = None
    axes: tuple[Point, Point] = ((1.0, 0.0), (0.0, 1.0))

    def mapping(self, pixels: Point, bias: Point = (0, 0)) -> Affine:
        sx, sy = self.size[0] / pixels[0], self.size[1] / pixels[1]
        return Affine(
            self.axes[0][0] * sx,
            self.axes[1][0] * sy,
            self.axes[0][1] * sx,
            self.axes[1][1] * sy,
            self.origin[0] + bias[0],
            self.origin[1] + bias[1],
        )

    def bounds(self, bias: Point = (0, 0)) -> tuple[float, float, float, float]:
        mapping = self.mapping((1, 1), bias)
        corners = [mapping.point(p) for p in ((0, 0), (1, 0), (1, 1), (0, 1))]
        xs, ys = zip(*corners)
        return min(xs), min(ys), max(xs), max(ys)

    def box(self, bias: Point = (0, 0)) -> Box:
        return cast(Box, tuple(round(value) for value in self.bounds(bias)))

    def reframe(self, box: Box, bias: Point) -> Placement:
        """Reframe on the existing rect's pixel grid, retaining subpixel origin.

        Snapping absolute world coordinates would resample every untouched face
        when their shared rect is expanded. Round relative edges instead.
        """
        if box == self.box(bias):
            return self
        mapping = self.mapping(self.size, bias)
        inverse = mapping.inverse()
        x1, y1, x2, y2 = box
        corners = [inverse.point(p) for p in ((x1, y1), (x2, y1), (x2, y2), (x1, y2))]
        xs, ys = zip(*corners)
        low, high = (round(min(xs)), round(min(ys))), (round(max(xs)), round(max(ys)))
        origin = self.mapping(self.size).point(low)
        size = high[0] - low[0], high[1] - low[1]
        return replace(self, origin=origin, size=size)


@dataclass
class Asset:
    key: str
    name: str
    kind: Kind
    texture: ObjectRef
    original: Image.Image  # RGBA, bottom-left origin (rows increase upward)
    placement: Placement | None = None
    sprite: ObjectRef | None = None
    mesh: ObjectRef | None = None
    raw_size: tuple[int, int] | None = None
    mesh_size: tuple[int, int] | None = None
    mesh_image: Image.Image | None = None
    source: Image.Image | None = None
    replacement: Image.Image | None = None
    replacement_box: Box | None = None
    behaviour: ObjectRef | None = None
    texture_name: str = ""
    preserve_aspect: bool = False

    @property
    def modified(self) -> bool:
        return self.replacement is not None

    def decoded(self) -> Image.Image:
        image = self.mesh_image if self.mesh_image is not None else self.original
        size = self.raw_size
        if size is not None and image.size != size:
            image = image.crop((0, 0, *size))
        return image

    def image(self) -> Image.Image:
        return self.replacement if self.replacement is not None else self.decoded()


@dataclass
class EditOptions:
    face_mode: FaceMode = FaceMode.OFF
    compression: str = "original"
    extensions: dict[str, Box] = field(default_factory=dict)


@dataclass
class Project:
    metadata: Path
    name: str
    size: tuple[int, int]
    bias: Point
    assets: list[Asset]
    face: Placement | None = None
    dependencies: tuple[str, ...] = ()
    options: EditOptions = field(default_factory=EditOptions)

    @property
    def stem(self) -> str:
        return self.metadata.name.removesuffix("_ex").removesuffix("_n").lower()

    @property
    def paintings(self) -> list[Asset]:
        return [a for a in self.assets if a.kind == Kind.PAINTING]

    @property
    def modified(self) -> list[Asset]:
        return [a for a in self.assets if a.modified]

    def asset(self, key: str) -> Asset:
        return next(a for a in self.assets if a.key == key)

    def preferred(self) -> Asset:
        """Smallest painting containing the face; never choose an unrelated decoration."""
        candidates = [asset for asset in self.paintings if asset.placement is not None]
        if self.face:
            fx1, fy1, fx2, fy2 = self.face.box()
            containing = [
                a
                for a in candidates
                if a.placement
                and a.placement.box()[0] <= fx1
                and a.placement.box()[1] <= fy1
                and a.placement.box()[2] >= fx2
                and a.placement.box()[3] >= fy2
            ]
            if containing:
                candidates = containing
        if not candidates:
            raise ValueError(
                Message(QT_TRANSLATE_NOOP("Messages", "The project has no available painting layer"))
            )
        return min(
            candidates,
            key=lambda a: cast(Placement, a.placement).size[0] * cast(Placement, a.placement).size[1],
        )


@dataclass(frozen=True)
class IconPreset:
    size: tuple[int, int]
    pivot: Point = (0.5, 0.6)
    scale: float = 0.6
    angle: float = 0.0


def default_presets() -> dict[str, IconPreset]:
    return {
        "shipyardicon": IconPreset((192, 256), (0.5, 0.7)),
        "herohrzicon": IconPreset((360, 80), (0.2, 0.6)),
        "squareicon": IconPreset((116, 116)),
    }
