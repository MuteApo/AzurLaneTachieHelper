"""Deferred application messages; Qt translation happens only at the presentation boundary."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override


def QT_TRANSLATE_NOOP(context: str, source: str) -> str:
    """Mark source text for Qt's lupdate without importing Qt into the domain."""
    return source


@dataclass(frozen=True)
class Message:
    source: str
    args: tuple[object, ...] = ()

    @override
    def __str__(self) -> str:
        return self.source.format(*self.args)


type Progress = Callable[[str | Message, int, int], None]


def no_progress(message: str | Message, current: int = 0, total: int = 0):
    pass
