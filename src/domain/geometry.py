"""Planar affine transforms; coordinates and image rows both increase upward."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Affine:
    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 1.0
    x: float = 0.0
    y: float = 0.0

    def point(self, point: tuple[float, float]) -> tuple[float, float]:
        x, y = point
        return self.a * x + self.b * y + self.x, self.c * x + self.d * y + self.y

    def __matmul__(self, other: Affine) -> Affine:
        x, y = self.point((other.x, other.y))
        return Affine(
            self.a * other.a + self.b * other.c,
            self.a * other.b + self.b * other.d,
            self.c * other.a + self.d * other.c,
            self.c * other.b + self.d * other.d,
            x,
            y,
        )

    def inverse(self) -> Affine:
        determinant = self.a * self.d - self.b * self.c
        a, b, c, d = self.d / determinant, -self.b / determinant, -self.c / determinant, self.a / determinant
        return Affine(a, b, c, d, -a * self.x - b * self.y, -c * self.x - d * self.y)

    def pillow(self) -> tuple[float, float, float, float, float, float]:
        return self.a, self.b, self.x, self.c, self.d, self.y
