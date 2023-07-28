from typing import Callable, Optional

import numpy as np
from PIL import Image
from typing_extensions import Self
from UnityPy.classes import GameObject, Mesh, MonoBehaviour, RectTransform, Texture2D, PPtr, Sprite
from UnityPy.enums import ClassIDType
from UnityPy.math import Quaternion, Vector2, Vector3


class Layer:
    def __init__(self, rt: RectTransform, parent: Self = None):
        self.rt = rt
        self.parent = parent
        self.child: list[Self] = [Layer(x.read(), self) for x in rt.m_Children]

    def __repr__(self) -> str:
        attrs = [
            # "localRotation",
            # "localPosition",
            # "localScale",
            # "anchorMin",
            # "anchorMax",
            # "anchoredPosition",
            "sizeDelta",
            # "pivot",
            # "posMin",
            # "posMax",
            "rawSpriteSize",
            "texture2D",
            "rawMesh",
        ]
        items = [""]
        for x in attrs:
            if hasattr(self, x):
                y = getattr(self, x)
                if y is not None:
                    items += [f"{x[0].capitalize()}{x[1:]}: {y}"]

        txt = "\n       ".join(items)
        name = self.sprite.name if self.sprite is not None else self.name
        return f"Layer@{self.posPivot} {name} {txt}"

    def __str__(self) -> str:
        return f"[INFO] {self.__repr__()}"

    def get_child(self, name: str) -> Optional[Self]:
        for x in self.child:
            if x.name == name:
                return x
        return None

    def flatten(self):
        res = {} if self.sprite is None else {self.sprite.name: self}
        for x in self.child:
            res |= x.flatten()
        return res

    def fetch(attr: str):
        attrs = ["m_AnchorMin", "m_AnchorMax", "m_AnchoredPosition", "m_SizeDelta", "m_Pivot"]

        def decor(func: Callable):
            def inner(self: Self):
                if not hasattr(self, attr):
                    if hasattr(self.rt, attr):
                        val = getattr(self.rt, attr)
                        if attr in attrs:
                            val = Vector2(val.x, val.y)
                    else:
                        val = None
                    setattr(self, attr, val)
                return func(self, getattr(self, attr))

            return inner

        return decor

    @property
    def name(self) -> str:
        return self.gameObject.name if self.gameObject else ""

    @property
    @fetch("m_PathID")
    def pathId(self, val: int) -> int:
        return val

    @property
    @fetch("m_GameObject")
    def gameObject(self, val: PPtr) -> GameObject:
        return val.read()

    @property
    def components(self) -> list[PPtr]:
        return self.gameObject.m_Components

    @property
    def monoBehaviour(self) -> Optional[MonoBehaviour]:
        if not hasattr(self, "m_MonoBehaviour"):
            for x in self.components:
                if x.type == ClassIDType.MonoBehaviour:
                    setattr(self, "m_MonoBehaviour", x.read())
                    return getattr(self, "m_MonoBehaviour")
            setattr(self, "m_MonoBehaviour", None)
        return getattr(self, "m_MonoBehaviour")

    @property
    def sprite(self) -> Optional[Sprite]:
        if not hasattr(self, "m_Sprite"):
            if self.monoBehaviour is not None:
                if hasattr(self.monoBehaviour, "m_Sprite"):
                    x = getattr(self.monoBehaviour, "m_Sprite")
                    y = x.read() if x.get_obj() is not None else None
                    setattr(self, "m_Sprite", y)
                    return getattr(self, "m_Sprite")
            setattr(self, "m_Sprite", None)
        return getattr(self, "m_Sprite")

    @property
    def texture2D(self) -> Optional[Texture2D]:
        if not hasattr(self, "m_Texture2D"):
            if self.sprite is not None:
                x = self.sprite.m_RD.texture.read()
                setattr(self, "m_Texture2D", x)
                return getattr(self, "m_Texture2D")
            setattr(self, "m_Texture2D", None)
        return getattr(self, "m_Texture2D")

    @property
    def rawMesh(self) -> Optional[Mesh]:
        if not hasattr(self, "m_Mesh"):
            if self.monoBehaviour is not None:
                if hasattr(self.monoBehaviour, "mMesh"):
                    x = getattr(self.monoBehaviour, "mMesh")
                    y = x.read() if x.get_obj() is not None else None
                    setattr(self, "m_Mesh", y)
                    return getattr(self, "m_Mesh")
            setattr(self, "m_Mesh", None)
        return getattr(self, "m_Mesh")

    @property
    def rawSpriteSize(self) -> Optional[tuple[int, int]]:
        if not hasattr(self, "m_RawSpriteSize"):
            if self.monoBehaviour is not None:
                if hasattr(self.monoBehaviour, "mRawSpriteSize"):
                    x = getattr(self.monoBehaviour, "mRawSpriteSize")
                    setattr(self, "m_RawSpriteSize", (int(x.x), int(x.y)))
                    return getattr(self, "m_RawSpriteSize")
            setattr(self, "m_RawSpriteSize", None)
        return getattr(self, "m_RawSpriteSize")

    @property
    @fetch("m_LocalRotation")
    def localRotation(self, val: Quaternion) -> tuple[float, float]:
        return val.X, val.Y

    @property
    @fetch("m_LocalPosition")
    def localPosition(self, val: Vector3) -> tuple[float, float]:
        return val.X, val.Y

    @property
    @fetch("m_LocalScale")
    def localScale(self, val: Vector3) -> tuple[float, float]:
        return val.X, val.Y

    @property
    @fetch("m_AnchorMin")
    def anchorMin(self, val: Vector2) -> tuple[float, float]:
        return val.X, val.Y

    @property
    @fetch("m_AnchorMax")
    def anchorMax(self, val: Vector2) -> tuple[float, float]:
        return val.X, val.Y

    @property
    @fetch("m_AnchoredPosition")
    def anchoredPosition(self, val: Vector2) -> tuple[float, float]:
        return val.X, val.Y

    @property
    @fetch("m_SizeDelta")
    def sizeDelta(self, val: Vector2) -> tuple[int, int]:
        return round(val.X), round(val.Y)

    @property
    @fetch("m_Pivot")
    def pivot(self, val: Vector2) -> tuple[float, float]:
        return val.X, val.Y

    @property
    def posAnchor(self) -> tuple[float, float]:
        anchorCenter = np.mean([self.anchorMin, self.anchorMax], 0)
        x, y = np.multiply(self.parent.sizeDelta, anchorCenter)
        return x, y

    @property
    def posPivot(self) -> tuple[float, float]:
        if self.parent is None:
            return 0.0, 0.0
        x, y = np.add(self.parent.posPivot, self.localPosition)
        return x, y

    @property
    def posMin(self) -> tuple[float, float]:
        sizedPivot = np.multiply(self.sizeDelta, self.pivot)
        x, y = np.subtract(self.posPivot, sizedPivot)
        return x, y

    @property
    def posMax(self) -> tuple[float, float]:
        sizedPivot = np.multiply(self.sizeDelta, 1 - np.array(self.pivot))
        x, y = np.add(self.posPivot, sizedPivot)
        return x, y

    @property
    def mesh(self) -> dict[str, np.ndarray]:
        w, h = self.texture2D.image.size
        if self.rawMesh is None:
            return {
                "v": np.array([[0, 0], [0, h], [w, h], [w, 0]]),
                "vt": np.array([[0, 0], [0, h], [w, h], [w, 0]]),
                "f": np.array([[0, 1, 2, 3]]),
            }
        return {
            "v": np.array(self.rawMesh.m_Vertices).reshape((-1, 3))[:, :2],
            "vt": np.array(self.rawMesh.m_UV0).reshape((-1, 2)) * (w, h),
            "f": np.array(self.rawMesh.m_Indices).reshape((-1, 6))[:, (0, 1, 3, 4)],
        }

    @property
    def tex(self) -> Image.Image:
        return self.texture2D.image.transpose(Image.FLIP_TOP_BOTTOM)

    @property
    def whs(self) -> tuple[int, int]:
        return self.texture2D.image.size
