from typing import Callable, Optional

from PIL import Image
from typing_extensions import Self
from UnityPy.classes import (
    GameObject,
    Mesh,
    MonoBehaviour,
    PPtr,
    RectTransform,
    Sprite,
    Texture2D,
)
from UnityPy.enums import ClassIDType
from UnityPy.math import Quaternion, Vector3

from .utility import prod
from .Vector import Vector2


class Layer:
    def __init__(self, rt: RectTransform, parent: Self = None):
        self.rt = rt
        self.parent = parent
        self.depth = 1 if parent is None else parent.depth + 1
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
            "posMin",
            "posMax",
            "meshSize",
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
        return f"Layer@{self.depth} {self.name} {txt}"

    def __str__(self) -> str:
        return f"[INFO] {self.__repr__()}"

    def get_child(self, name: str) -> Optional[Self]:
        for x in self.child:
            if x.name == name:
                return x
        return None

    def flatten(self):
        res = {}
        if self.sprite is not None:
            name = self.sprite.name if self.name in ["part"] else self.name
            res[name] = self
        for x in self.child:
            res |= x.flatten()
        return res

    def contain(self, l: float, b: float, r: float, t: float) -> bool:
        if l < self.posMin[0] or b < self.posMin[1]:
            return False
        if r > self.posMax[0] or t > self.posMax[1]:
            return False
        return True

    def fetch(attr: str):
        attrs = ["m_AnchorMin", "m_AnchorMax", "m_AnchoredPosition", "m_SizeDelta", "m_Pivot"]

        def decor(func: Callable):
            def inner(self: Self):
                if hasattr(self.rt, attr):
                    val = getattr(self.rt, attr)
                    if attr in attrs:
                        val = Vector2(val.x, val.y)
                else:
                    val = None
                return func(self, val)

            return inner

        return decor

    @property
    def name(self) -> str:
        return self.gameObject.name if self.gameObject else ""

    @property
    def pathId(self) -> int:
        return self.rt.path_id

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
    def rawSpriteSize(self) -> Optional[Vector2]:
        if not hasattr(self, "m_RawSpriteSize"):
            if self.monoBehaviour is not None:
                if hasattr(self.monoBehaviour, "mRawSpriteSize"):
                    x = getattr(self.monoBehaviour, "mRawSpriteSize")
                    setattr(self, "m_RawSpriteSize", Vector2(x.x, x.y))
                    return getattr(self, "m_RawSpriteSize")
            setattr(self, "m_RawSpriteSize", None)
        return getattr(self, "m_RawSpriteSize")

    @property
    @fetch("m_LocalRotation")
    def localRotation(self, val: Quaternion) -> Vector2:
        return Vector2(val.X, val.Y)

    @property
    @fetch("m_LocalPosition")
    def localPosition(self, val: Vector3) -> Vector2:
        return Vector2(val.X, val.Y)

    @property
    @fetch("m_LocalScale")
    def localScale(self, val: Vector3) -> Vector2:
        return val

    @property
    @fetch("m_AnchorMin")
    def anchorMin(self, val: Vector2) -> Vector2:
        return val

    @property
    @fetch("m_AnchorMax")
    def anchorMax(self, val: Vector2) -> Vector2:
        return val

    @property
    @fetch("m_AnchoredPosition")
    def anchoredPosition(self, val: Vector2) -> Vector2:
        return val

    @property
    @fetch("m_SizeDelta")
    def sizeDelta(self, val: Vector2) -> Vector2:
        return val

    @property
    @fetch("m_Pivot")
    def pivot(self, val: Vector2) -> Vector2:
        return val

    @property
    def posAnchor(self) -> Vector2:
        return self.parent.sizeDelta * (self.anchorMin + self.anchorMax) / 2

    @property
    def posPivot(self) -> Vector2:
        if self.parent is None:
            return Vector2.zero()
        return self.parent.posPivot + self.localPosition

    @property
    def posMin(self) -> Vector2:
        return self.posPivot - self.sizeDelta * self.pivot

    @property
    def posMax(self) -> Vector2:
        return self.posMin + self.canvasSize

    @property
    def box(self) -> tuple[float, float, float, float]:
        return *self.posMin, *self.posMax

    @property
    def mesh(self) -> list[tuple]:
        if not hasattr(self, "_mesh"):
            if self.texture2D is None:
                setattr(self, "_mesh", None)
            else:
                w, h = self.texture2D.image.size
                val = []
                if self.rawMesh is None:
                    val += [((0, 0, w, h), (0, 0, 0, h, w, h, w, 0))]
                else:
                    v = self.rawMesh.m_Vertices
                    v = [(round(v[i]), round(v[i + 1])) for i in range(0, len(v), 3)]
                    t = self.rawMesh.m_UV0
                    t = [(round(t[i] * w), round(t[i + 1] * h)) for i in range(0, len(t), 2)]
                    f = self.rawMesh.m_Indices
                    for i in range(0, len(f), 6):
                        val += [
                            (
                                (*v[f[i]], *v[f[i + 3]]),
                                (*t[f[i]], *t[f[i + 1]], *t[f[i + 3]], *t[f[i + 4]]),
                            )
                        ]
                setattr(self, "_mesh", val)
        return getattr(self, "_mesh")

    @property
    def tex(self) -> Image.Image:
        if not hasattr(self, "_tex"):
            img = self.texture2D.image.transpose(Image.FLIP_TOP_BOTTOM)
            setattr(self, "_tex", img)
        return getattr(self, "_tex")

    @property
    def meshSize(self) -> Vector2:
        if not hasattr(self, "_mesh_size"):
            if self.mesh is None:
                setattr(self, "_mesh_size", None)
            else:
                v = [x[0] for x in self.mesh]
                w = max([x[2] for x in v]) + 1
                h = max([x[3] for x in v]) + 1
                setattr(self, "_mesh_size", Vector2(w, h))
        return getattr(self, "_mesh_size")

    @property
    def spriteSize(self) -> Vector2:
        if self.rawSpriteSize is None:
            return self.meshSize
        elif prod(self.meshSize) > prod(self.rawSpriteSize):
            return self.meshSize
        else:
            return self.rawSpriteSize

    @property
    def canvasSize(self) -> Vector2:
        if self.spriteSize is None:
            return self.sizeDelta
        elif prod(self.spriteSize) > prod(self.sizeDelta):
            return self.spriteSize
        else:
            return self.sizeDelta

    def decode(self) -> Image.Image:
        if not hasattr(self, "_dec_tex"):
            size = self.spriteSize.round().tuple()
            dec = self.tex.transform(size, Image.MESH, self.mesh)
            setattr(self, "_dec_tex", dec)
        return getattr(self, "_dec_tex")
