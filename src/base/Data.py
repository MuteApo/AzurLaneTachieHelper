import re
from dataclasses import dataclass
from enum import Enum

from .Vector import Vector2


class FaceModeType(Enum):
    Off = 0
    Auto = 1
    Custom = 2


@dataclass
class MetaInfo:
    path: str
    name: str
    size: Vector2
    bias: Vector2

    @property
    def name_stem(self):
        return self.name.removesuffix("_ex").removesuffix("_n").lower()

    def __str__(self):
        return f"<MetaInfo name={self.name}, size={self.size}, bias={self.bias}>: {self.path}"


def parse_icon_preset(data: str):
    num = r"-?\d+(?:\.\d+)?"
    pivot_match = re.search(rf"pivot=\(({num}),\s*({num})\)", data)
    scale_match = re.search(rf"scale=({num})", data)
    angle_match = re.search(rf"angle=({num})", data)

    pivot = Vector2(float(pivot_match.group(1)), float(pivot_match.group(2)))
    scale = float(scale_match.group(1))
    angle = float(angle_match.group(1))

    return dict(pivot=pivot, scale=scale, angle=angle)


class IconPreset:
    def __init__(
        self,
        size: Vector2[int] | tuple[int, int],
        pivot: Vector2[float] | tuple[float, float],
        scale: float,
        angle: float,
    ):
        self.size = Vector2(size)
        self.pivot = Vector2(pivot)
        self.scale = scale
        self.angle = angle

    def __getitem__(self, item: str) -> float | Vector2:
        return getattr(self, item)

    def __setitem__(self, key: str, value: float | Vector2):
        setattr(self, key, Vector2(value) if isinstance(value, tuple) else value)

    def __repr__(self) -> str:
        return self.to_dict().__repr__()

    def to_dict(self) -> dict:
        return dict(size=self.size.tuple(), pivot=self.pivot.tuple(), scale=self.scale, angle=self.angle)

    def apply(self, pivot: Vector2 | tuple[float, float], scale: float, angle: float):
        self.pivot += Vector2(pivot)
        self.scale += scale
        self.angle += angle


class IconPresets:
    def __init__(self):
        self.shipyardicon = IconPreset((192, 256), (0.5, 0.7), 0.6, 0.0)
        self.herohrzicon = IconPreset((360, 80), (0.2, 0.6), 0.6, 0.0)
        self.squareicon = IconPreset((116, 116), (0.5, 0.6), 0.6, 0.0)

    def __getitem__(self, item: str) -> IconPreset:
        return getattr(self, item)

    def __setitem__(self, key: str, value: IconPreset):
        setattr(self, key, value)

    def __repr__(self) -> str:
        return self.to_dict().__repr__()

    def to_dict(self):
        return dict(shipyardicon=self.shipyardicon, herohrzicon=self.herohrzicon, squareicon=self.squareicon)
