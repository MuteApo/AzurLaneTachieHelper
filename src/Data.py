from dataclasses import dataclass

from typing_extensions import Self

from .Vector import Vector2


@dataclass
class MetaInfo:
    path: str
    name: str
    size: Vector2
    bias: Vector2


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

    @property
    def aspect_ratio(self):
        return self.tex2d.X / self.tex2d.Y

    @classmethod
    def default(cls) -> dict[str, Self]:
        return {
            "shipyardicon": IconPreset(
                Vector2(192, 256), Vector2(192, 256), Vector2(0.5, 0.7), 0.6, 0
            ),
            "squareicon": IconPreset(
                Vector2(116, 116), Vector2(116, 116), Vector2(0.5, 0.6), 0.6, 0
            ),
            "herohrzicon": IconPreset(
                Vector2(272, 80), Vector2(360, 80), Vector2(0.2, 0.6), 0.6, 0
            ),
        }
