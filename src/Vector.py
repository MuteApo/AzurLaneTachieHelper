from math import ceil, floor

from typing_extensions import Self


class Vector2:
    def __init__(self, *args):
        if len(args) == 1:
            if isinstance(args[0], Vector2):
                self.X, self.Y = args[0]
            elif isinstance(args[0], (float, int)):
                self.X = self.Y = args[0]
            elif isinstance(args[0], (list, tuple)):
                self.X, self.Y = args[0]
        elif len(args) == 2:
            self.X, self.Y = args
            assert isinstance(self.X, (float, int))
            assert isinstance(self.Y, (float, int))
        else:
            raise ValueError(args)

    def __repr__(self) -> str:
        return f"({self.X}, {self.Y})"

    def __getitem__(self, index):
        return (self.X, self.Y)[index]

    def __setitem__(self, index, value):
        if index == 0:
            self.X = value
        elif index == 1:
            self.Y = value
        else:
            raise IndexError("Index out of range")

    def __hash__(self):
        return self.X.__hash__() ^ (self.Y.__hash__() << 2)

    def __eq__(self, other):
        if isinstance(other, Vector2):
            return self.X == other.X and self.Y == other.Y
        else:
            return False

    def __ne__(lhs, rhs):
        return not (lhs == rhs)

    def __le__(self, other):
        return self.X < other.X or self.X == other.X and self.Y < other.Y

    def __add__(self, other) -> Self:
        if not isinstance(other, Vector2):
            other = Vector2(other)
        return Vector2(self.X + other.X, self.Y + other.Y)

    def __sub__(self, other) -> Self:
        if not isinstance(other, Vector2):
            other = Vector2(other)
        return Vector2(self.X - other.X, self.Y - other.Y)

    def __mul__(self, other) -> Self:
        if not isinstance(other, Vector2):
            other = Vector2(other)
        return Vector2(self.X * other.X, self.Y * other.Y)

    def __truediv__(self, other) -> Self:
        if not isinstance(other, Vector2):
            other = Vector2(other)
        return Vector2(self.X / other.X, self.Y / other.Y)

    def round(self):
        return Vector2(round(self.X), round(self.Y))

    def floor(self):
        return Vector2(floor(self.X), floor(self.Y))

    def ceil(self):
        return Vector2(ceil(self.X), ceil(self.Y))

    @staticmethod
    def zero():
        return Vector2(0, 0)

    @staticmethod
    def one():
        return Vector2(1, 1)
