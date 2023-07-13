from typing import Optional

import numpy as np
from PIL import Image
from typing_extensions import Self
from UnityPy.classes import GameObject, Mesh, MonoBehaviour, RectTransform, Texture2D
from UnityPy.enums import ClassIDType
from UnityPy.math import Quaternion, Vector3


def vec2array(vec) -> np.ndarray:
    if isinstance(vec, Quaternion):
        return np.array([vec.X, vec.Y, vec.Z, vec.W])
    if isinstance(vec, Vector3):
        return np.array([vec.X, vec.Y, vec.Z])
    return np.array([vec.x, vec.y])


class Layer:
    def __init__(self, rt: RectTransform, parent: Self = None):
        go: GameObject = rt.m_GameObject.read()
        self._name = go.name.lower()
        self._local_rotation = vec2array(rt.m_LocalRotation)
        self._local_position = vec2array(rt.m_LocalPosition)[:2]
        self._local_scale = vec2array(rt.m_LocalScale)[:2]
        self._anchor_min = vec2array(rt.m_AnchorMin)
        self._anchor_max = vec2array(rt.m_AnchorMax)
        self._anchored_position = vec2array(rt.m_AnchoredPosition)
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
            self._pos_pivot = np.array([0.0, 0.0])
        else:
            self._pos_pivot = parent._pos_pivot + self._local_position

        self._parent = parent
        self._path_id = rt.path_id

    def __repr__(self) -> str:
        items = [
            "",
            # f"LocalRotation: {self.localRotation}",
            # f"LocalPosition: {self.localPosition}",
            # f"LocalScale: {self.localScale}",
            # f"AnchorMin: {self.anchorMin}",
            # f"AnchorMax: {self.anchorMax}",
            # f"AnchoredPosition: {self.anchoredPosition}",
            f"SizeDelta: {self.sizeDelta}",
            # f"Pivot: {self.pivot}",
            # f"PosMin: {self.posMin}",
            # f"PosMax: {self.posMax}",
        ]
        if hasattr(self, "_raw_sprite_size"):
            items += [f"RawSpriteSize: {self.rawSpriteSize}"]
        if hasattr(self, "_tex"):
            items += [f"Texture: {self._tex}"]
        if hasattr(self, "_mesh"):
            items += [f"Mesh: {self._mesh}" if self._mesh is not None else "Mesh: None"]
        txt = "\n       ".join(items)
        return f"Layer@{self.posPivot} {self.name} {txt}"

    def __str__(self) -> str:
        return f"[INFO] {self.__repr__()}"

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
    def pathId(self) -> int:
        return self._path_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def parent(self) -> Optional[Self]:
        return self._parent

    @property
    def localRotation(self) -> tuple[float, float, float, float]:
        x, y, z, w = self._local_rotation
        return x, y, z, w

    @property
    def localPosition(self) -> tuple[float, float]:
        x, y = self._local_position
        return x, y

    @property
    def localScale(self) -> tuple[float, float]:
        x, y = self._local_scale
        return x, y

    @property
    def anchorMin(self) -> tuple[float, float]:
        x, y = self._anchor_min
        return x, y

    @property
    def anchorMax(self) -> tuple[float, float]:
        x, y = self._anchor_max
        return x, y

    @property
    def anchoredPosition(self) -> tuple[float, float]:
        x, y = self._anchored_position
        return x, y

    @property
    def sizeDelta(self) -> tuple[int, int]:
        x, y = self._size_delta
        return int(x), int(y)

    @property
    def scaledSizeDelta(self) -> tuple[int, int]:
        x, y = self._size_delta * self._local_scale
        return int(x), int(y)

    @property
    def pivot(self) -> tuple[float, float]:
        x, y = self._pivot
        return x, y

    @property
    def rawSpriteSize(self) -> tuple[int, int]:
        x, y = self._raw_sprite_size
        return int(x), int(y)

    @property
    def posAnchor(self) -> tuple[float, float]:
        x, y = self.parent._size_delta * (self._anchor_min + self._anchor_max) / 2
        return x, y

    @property
    def posPivot(self) -> tuple[float, float]:
        x, y = self._pos_pivot
        return x, y

    @property
    def posMin(self) -> tuple[int, int]:
        x, y = self._pos_pivot - self._size_delta * self._pivot
        return round(x), round(y)

    @property
    def posMax(self) -> tuple[int, int]:
        x, y = self._pos_pivot + self._size_delta * (1 - self._pivot)
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
