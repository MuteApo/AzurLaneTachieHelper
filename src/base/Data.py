import re
from dataclasses import dataclass
from typing import Optional, Self

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
        return f"<angle={self.angle}, scale={self.scale}, pivot={self.pivot}>"

    def apply(self, pivot: Vector2, scale: float, angle: float):
        self.pivot += pivot
        self.scale += scale
        self.angle += angle

    @classmethod
    def from_config(cls, kind: str, repr: Optional[str] = None) -> Self:
        if repr is None:
            return cls.default(kind)
        num = r"-?\d+\.\d+|-?\d+"
        pivot = re.search(rf"pivot=\(({num}),\s*({num})\)", repr)
        pivot = Vector2(eval(pivot.group(1)), eval(pivot.group(2)))
        scale = eval(re.search(rf"scale=({num})", repr).group(1))
        angle = eval(re.search(rf"angle=({num})", repr).group(1))
        return cls.kind2cls(kind)(pivot=pivot, scale=scale, angle=angle)

    @classmethod
    def kind2cls(cls, kind: str) -> Self:
        return {
            "shipyardicon": ShipyardiconPreset,
            "herohrzicon": HerohrziconPreset,
            "squareicon": SquareiconPreset,
        }[kind.lower()]

    @classmethod
    def default(cls, kind: str) -> Self:
        return cls.kind2cls(kind)()


class ShipyardiconPreset(IconPreset):
    def __init__(
        self,
        sprite: Vector2 = Vector2(192, 256),
        tex2d: Vector2 = Vector2(192, 256),
        pivot: Vector2 = Vector2(0.5, 0.7),
        scale: float = 0.6,
        angle: float = 0,
    ):
        super().__init__(sprite, tex2d, pivot, scale, angle)


class HerohrziconPreset(IconPreset):
    def __init__(
        self,
        sprite: Vector2 = Vector2(272, 80),
        tex2d: Vector2 = Vector2(360, 80),
        pivot: Vector2 = Vector2(0.2, 0.6),
        scale: float = 0.6,
        angle: float = 0,
    ):
        super().__init__(sprite, tex2d, pivot, scale, angle)


class SquareiconPreset(IconPreset):
    def __init__(
        self,
        sprite: Vector2 = Vector2(116, 116),
        tex2d: Vector2 = Vector2(116, 116),
        pivot: Vector2 = Vector2(0.5, 0.6),
        scale: float = 0.6,
        angle: float = 0,
    ):
        super().__init__(sprite, tex2d, pivot, scale, angle)
