import re
from dataclasses import dataclass

from typing_extensions import Self

from .Vector import Vector2


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


@dataclass
class IconPreset:
    sprite: Vector2
    tex2d: Vector2
    pivot: Vector2
    scale: float
    angle: float

    def __repr__(self) -> str:
        return f"<IconPreset angle={self.angle}, scale={self.scale}, pivot={self.pivot}>"

    def apply(self, pivot: Vector2, scale: float, angle: float):
        self.pivot += pivot
        self.scale += scale
        self.angle += angle

    def from_repr(self, repr: str) -> Self:
        num = r"-?\d+\.\d+|-?\d+"
        self.angle = eval(re.search(rf"angle=({num})", repr).group(1))
        self.scale = eval(re.search(rf"scale=({num})", repr).group(1))
        pivot = re.search(rf"pivot=\(({num}),\s*({num})\)", repr)
        self.pivot = Vector2(eval(pivot.group(1)), eval(pivot.group(2)))
        return self

    @classmethod
    def defaults(cls) -> dict[str, Self]:
        return {
            "shipyardicon": IconPreset(Vector2(192, 256), Vector2(192, 256), Vector2(0.5, 0.7), 0.6, 0),
            "squareicon": IconPreset(Vector2(116, 116), Vector2(116, 116), Vector2(0.5, 0.6), 0.6, 0),
            "herohrzicon": IconPreset(Vector2(272, 80), Vector2(360, 80), Vector2(0.2, 0.6), 0.6, 0),
        }
