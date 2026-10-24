"""Unity Transform layout shared by decoding and writeback."""

import math
from dataclasses import dataclass
from typing import Any, cast

from domain.geometry import Affine
from domain.model import ObjectRef, Placement, Point


def vector_xy(value, default=(0.0, 0.0)):
    return (value.x, value.y) if value is not None else default


@dataclass
class TransformNode:
    transform: Any
    parent: TransformNode | None
    name: str
    local_size: Point
    matrix: Affine  # Transform's pivot-local coordinates -> prefab coordinates
    pivot: tuple[float, float]
    anchored: tuple[float, float]

    @property
    def scale(self) -> Point:
        return math.hypot(self.matrix.a, self.matrix.c), math.hypot(self.matrix.b, self.matrix.d)

    @property
    def size(self) -> Point:
        return self.local_size[0] * self.scale[0], self.local_size[1] * self.scale[1]

    @property
    def origin(self) -> Point:
        return self.matrix.point((-self.local_size[0] * self.pivot[0], -self.local_size[1] * self.pivot[1]))

    @property
    def pivot_position(self) -> Point:
        return self.matrix.x, self.matrix.y

    def placement(self, rect: ObjectRef | None = None) -> Placement:
        sx, sy = self.scale
        return Placement(
            self.origin,
            self.size,
            self.pivot,
            self.anchored,
            self.scale,
            rect,
            ((self.matrix.a / sx, self.matrix.c / sx), (self.matrix.b / sy, self.matrix.d / sy)),
        )


def transform_node(transform, parent=None) -> TransformNode:
    """Resolve layout before applying local TRS, as Unity RectTransform does.

    Parent rect dimensions are unscaled; anchors place the child's pivot in the
    parent's local rect. Matrices then carry rotation/scale through the hierarchy.
    The root is the export reference frame, independent of its scene placement.
    """
    go = transform.m_GameObject.deref_parse_as_object()
    is_rect = hasattr(transform, "m_SizeDelta")
    pivot = vector_xy(getattr(transform, "m_Pivot", None))
    anchored = vector_xy(getattr(transform, "m_AnchoredPosition", None))
    delta = vector_xy(getattr(transform, "m_SizeDelta", None))
    anchor_min = vector_xy(getattr(transform, "m_AnchorMin", None))
    anchor_max = vector_xy(getattr(transform, "m_AnchorMax", None))
    if parent is None:
        size = delta
        matrix = Affine(x=size[0] * pivot[0], y=size[1] * pivot[1])
    else:
        parent_rect = hasattr(parent.transform, "m_SizeDelta")
        size = (
            tuple(delta[i] + (anchor_max[i] - anchor_min[i]) * parent.local_size[i] for i in range(2))
            if is_rect and parent_rect
            else delta
        )
        if is_rect and parent_rect:
            offset = tuple(
                anchored[i]
                + parent.local_size[i]
                * (anchor_min[i] + (anchor_max[i] - anchor_min[i]) * pivot[i] - parent.pivot[i])
                for i in range(2)
            )
        else:
            offset = vector_xy(transform.m_LocalPosition)
        sx, sy = vector_xy(transform.m_LocalScale, (1, 1))
        q = transform.m_LocalRotation
        local = Affine(
            (1 - 2 * (q.y * q.y + q.z * q.z)) * sx,
            2 * (q.x * q.y - q.z * q.w) * sy,
            2 * (q.x * q.y + q.z * q.w) * sx,
            (1 - 2 * (q.x * q.x + q.z * q.z)) * sy,
            *offset,
        )
        matrix = parent.matrix @ local
    return TransformNode(transform, parent, go.m_Name, cast(Point, size), matrix, pivot, anchored)
