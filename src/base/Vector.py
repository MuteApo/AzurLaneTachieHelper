from math import ceil, cos, floor, sin, sqrt
from typing import Generic, TypeVar

T = TypeVar("T", float, int)


class Vector2(Generic[T]):
    def __init__(self, *args):
        if len(args) == 1:
            if isinstance(args[0], (Vector2, list, tuple)):
                self.X, self.Y = args[0]
            elif isinstance(args[0], (float, int)):
                self.X = self.Y = args[0]
            else:
                raise ValueError(args)
        elif len(args) == 2:
            self.X, self.Y = args
        else:
            raise ValueError(args)

    def __repr__(self):
        return f"({self.X}, {self.Y})"

    def __len__(self):
        return 2

    def __getitem__(self, index: int):
        match index:
            case 0:
                return self.X
            case 1:
                return self.Y
            case _:
                raise IndexError(f"Index {index} out of range")

    def __setitem__(self, index: int, value: T):
        match index:
            case 0:
                self.X = value
            case 1:
                self.Y = value
            case _:
                raise IndexError(f"Index {index} out of range")

    def __hash__(self) -> int:
        return self.X.__hash__() ^ (self.Y.__hash__() << 2)

    def __eq__(self, other) -> bool:
        if not isinstance(other, Vector2[T]):
            return False
        return self.X == other.X and self.Y == other.Y

    def __ne__(self, other) -> bool:
        return not self == other

    def __le__(self, other) -> bool:
        return self.X < other.X or self.X == other.X and self.Y < other.Y

    def __neg__(self):
        return Vector2(-self.X, -self.Y)

    def __add__(self, other):
        other = Vector2(other)
        return Vector2(self.X + other.X, self.Y + other.Y)

    def __sub__(self, other):
        other = Vector2(other)
        return Vector2(self.X - other.X, self.Y - other.Y)

    def __rsub__(self, other):
        other = Vector2(other)
        return Vector2(other.X - self.X, other.Y - self.Y)

    def __mul__(self, other):
        other = Vector2(other)
        return Vector2(self.X * other.X, self.Y * other.Y)

    def __rmul__(self, other):
        other = Vector2(other)
        return Vector2(other.X * self.X, other.Y * self.Y)

    def __truediv__(self, other):
        other = Vector2(other)
        return Vector2(self.X / other.X, self.Y / other.Y)

    def __floordiv__(self, other):
        other = Vector2(other)
        return Vector2(self.X // other.X, self.Y // other.Y)

    def __pow__(self, other):
        other = Vector2(other)
        return Vector2(self.X**other.X, self.Y**other.Y)

    def sqrt(self):
        return Vector2(sqrt(self.X), sqrt(self.Y))

    def round(self):
        return Vector2[int](round(self.X), round(self.Y))

    def floor(self):
        return Vector2[int](floor(self.X), floor(self.Y))

    def ceil(self):
        return Vector2[int](ceil(self.X), ceil(self.Y))

    def sum(self) -> float:
        return self.X + self.Y

    def prod(self) -> float:
        return self.X * self.Y

    def rotate(self, rad: float):
        x = self.X * cos(rad) - self.Y * sin(rad)
        y = self.X * sin(rad) + self.Y * cos(rad)
        return Vector2[float](x, y)

    def tuple(self) -> tuple[T, T]:
        return self.X, self.Y

    def dict(self) -> dict[str, T]:
        return {"x": self.X, "y": self.Y}
