from typing import Optional

import numpy as np
from PIL import Image
from typing_extensions import Self
from UnityPy.classes import GameObject, Mesh, MonoBehaviour, RectTransform, Texture2D
from UnityPy.enums import ClassIDType
from UnityPy.math import Vector3


def vec2array(vec) -> np.ndarray:
    if isinstance(vec, Vector3):
        return np.array([vec.X, vec.Y, vec.Z])
    return np.array([vec.x, vec.y])


class Layer:
    def __init__(self, rt: RectTransform, parent: Self = None):
        go: GameObject = rt.m_GameObject.read()
        self._name = go.name.lower()
        self._local_position = vec2array(rt.m_LocalPosition)[:2]
        self._size_delta = vec2array(rt.m_SizeDelta)
        self._pivot = vec2array(rt.m_Pivot)
        if go.m_Components[-1].type == ClassIDType.MonoBehaviour:
            mb: MonoBehaviour = go.m_Components[-1].read()
            sprite = mb.m_Sprite
            if sprite.get_obj() is not None:
                self._tex: Texture2D = sprite.read().m_RD.texture.read()
            if hasattr(mb, "mMesh"):
                obj = mb.mMesh.get_obj()
                self._mesh: Optional[Mesh] = obj.read() if obj is not None else None
            if hasattr(mb, "mRawSpriteSize"):
                self._raw_sprite_size = vec2array(mb.mRawSpriteSize)
        if parent is None:
            self._offset = self._pivot * self._size_delta
        else:
            self._offset = parent._offset + self._local_position

    def __repr__(self) -> str:
        items = [f"SizeDelta={self.sizeDelta}"]
        if hasattr(self, "_raw_sprite_size"):
            items += [f"RawSpriteSize={self.rawSpriteSize}"]
        if hasattr(self, "_tex"):
            items += [f"Texture={self._tex.name}@{self._tex.path_id}"]
        if hasattr(self, "_mesh"):
            items += [
                f"Mesh={self._mesh.name}@{self._mesh.path_id}"
                if self._mesh is not None
                else "Mesh=None"
            ]
        return f"<Layer {self.name}@{self.offset}> " + ", ".join(items)

    def _parse_mesh(self, mesh: Mesh) -> dict[str, np.ndarray]:
        return {
            "v": np.array(mesh.m_Vertices).reshape((-1, 3))[:, :2],
            "vt": np.array(mesh.m_UV0).reshape((-1, 2)),
            "f": np.array(mesh.m_Indices).reshape((-1, 6))[:, (0, 1, 3, 4)],
        }

    def _quad_mesh(self, w: float, h: float) -> dict[str, np.ndarray]:
        return {
            "v": np.array([[0, 0], [0, h], [w, h], [w, 0]]),
            "vt": np.array([[0, 0], [0, 1], [1, 1], [1, 0]]),
            "f": np.array([[0, 1, 2, 3]]),
        }

    @property
    def name(self) -> str:
        return self._name

    @property
    def localPosition(self) -> tuple[float, float]:
        return self._local_position[0], self._local_position[1]

    @property
    def sizeDelta(self) -> tuple[int, int]:
        return int(self._size_delta[0]), int(self._size_delta[1])

    @property
    def pivot(self) -> tuple[float, float]:
        return self._pivot[0], self._pivot[1]

    @property
    def rawSpriteSize(self) -> tuple[int, int]:
        return int(self._raw_sprite_size[0]), int(self._raw_sprite_size[1])

    @property
    def offset(self) -> tuple[int, int]:
        x, y = self._offset - self._pivot * self._size_delta
        return round(x), round(y)

    @property
    def mesh(self) -> dict[str, np.ndarray]:
        if self._mesh is None:
            return self._quad_mesh(*self._tex.image.size)
        return self._parse_mesh(self._mesh.read())

    @property
    def tex(self) -> Image.Image:
        return self._tex.image.transpose(Image.FLIP_TOP_BOTTOM)

    @property
    def whs(self) -> tuple[int, int]:
        return self._tex.image.size
