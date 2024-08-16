import os
from typing import Optional

from PIL import Image
from PySide6.QtCore import QDir
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

from ..logger import logger
from ..utility import open_and_transpose
from .Data import IconPreset, MetaInfo
from .Vector import Vector2


class Layer:
    def __init__(self, rt: RectTransform, parent: Self = None):
        self.rt = rt
        self.parent = parent
        self.depth = 1 if parent is None else parent.depth + 1
        self.child: list[Self] = [Layer(x.read(), self) for x in rt.m_Children]
        self.path: str = "Not Found"
        self.repl: Image.Image = None
        self.meta: MetaInfo = None

    def __repr__(self) -> str:
        return f"Layer@{self.depth} {self.name}"

    def __str__(self) -> str:
        attrs = ["texture2D", "mesh", "meshSize", "rawSpriteSize", "sizeDelta"]
        items = [""]
        for x in attrs:
            if hasattr(self, x):
                y = getattr(self, x)
                if y is not None:
                    items += [f"{x[0].capitalize()}{x[1:]}: {y.__repr__()}"]
        return "\n".join(items)

    def __contains__(self, other: Self) -> bool:
        if self.posMin[0] > other.posMin[0] or self.posMin[1] > other.posMin[1]:
            return False
        if self.posMax[0] < other.posMax[0] or self.posMax[1] < other.posMax[1]:
            return False
        return True

    def get_child(self, name: str) -> Optional[Self]:
        for x in self.child:
            if x.name == name:
                return x
        return None

    def flatten(self) -> dict[str, Self]:
        res = {}
        if self.sprite is not None:
            name = self.sprite.name if self.name in ["part"] else self.name
            res[name] = self
        for x in self.child:
            res |= x.flatten()
        return res

    @property
    def name(self) -> str:
        return self.gameObject.name if self.gameObject is not None else "Undefined"

    @property
    def pathId(self) -> int:
        return self.rt.path_id

    @property
    def gameObject(self) -> GameObject:
        return self.rt.m_GameObject.read()

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
        if self.monoBehaviour is None or not hasattr(self.monoBehaviour, "m_Sprite"):
            return None
        x = getattr(self.monoBehaviour, "m_Sprite")
        return x.read() if x.get_obj() is not None else None

    @property
    def texture2D(self) -> Optional[Texture2D]:
        if self.sprite is None:
            return None
        return self.sprite.m_RD.texture.read()

    @property
    def mesh(self) -> Optional[Mesh]:
        if self.monoBehaviour is None or not hasattr(self.monoBehaviour, "mMesh"):
            return None
        x = getattr(self.monoBehaviour, "mMesh")
        return x.read() if x.get_obj() is not None else None

    @property
    def rawSpriteSize(self) -> Optional[Vector2]:
        if self.monoBehaviour is None or not hasattr(self.monoBehaviour, "mRawSpriteSize"):
            return None
        x = getattr(self.monoBehaviour, "mRawSpriteSize")
        return Vector2(x.x, x.y)

    @property
    def localRotation(self) -> Vector2:
        val = self.rt.m_LocalRotation
        return Vector2(val.X, val.Y)

    @property
    def localPosition(self) -> Vector2:
        val = self.rt.m_LocalPosition
        return Vector2(val.X, val.Y)

    @property
    def localScale(self) -> Vector2:
        val = self.rt.m_LocalScale
        return Vector2(val.X, val.Y)

    @property
    def anchorMin(self) -> Vector2:
        val: Vector2 = self.rt.m_AnchorMin
        return Vector2(val.x, val.y)

    @property
    def anchorMax(self) -> Vector2:
        val: Vector2 = self.rt.m_AnchorMax
        return Vector2(val.x, val.y)

    @property
    def anchoredPosition(self) -> Vector2:
        val: Vector2 = self.rt.m_AnchoredPosition
        return Vector2(val.x, val.y)

    @property
    def sizeDelta(self) -> Vector2:
        val: Vector2 = self.rt.m_SizeDelta
        return Vector2(val.x, val.y)

    @property
    def pivot(self) -> Vector2:
        val: Vector2 = self.rt.m_Pivot
        return Vector2(val.x, val.y)

    @property
    def size(self) -> Vector2:
        val = self.sizeDelta
        if self.parent is not None:
            val += self.parent.sizeDelta * (self.anchorMax - self.anchorMin)
        return val

    @property
    def anchorPosition(self) -> Vector2:
        if self.parent is None:
            return Vector2(0)
        anchorMin = self.parent.size * self.anchorMin
        anchorMax = self.parent.size * self.anchorMax
        return self.parent.posMin + anchorMin * (1 - self.pivot) + anchorMax * self.pivot

    @property
    def pivotPosition(self) -> Vector2:
        return self.anchorPosition + self.anchoredPosition

    @property
    def posMin(self) -> Vector2:
        return self.pivotPosition - self.size * self.pivot

    @property
    def posMax(self) -> Vector2:
        return self.posMin + self.size

    @property
    def posBiased(self) -> Vector2:
        return self.posMin + self.meta.bias

    @property
    def buffer(self) -> list[tuple]:
        if not hasattr(self, "_mesh"):
            if self.texture2D is None:
                setattr(self, "_mesh", None)
            else:
                w, h = self.texture2D.image.size
                val = []
                if self.mesh is None:
                    val += [((0, 0, w, h), (0, 0, 0, h, w, h, w, 0))]
                else:
                    v = self.mesh.m_Vertices
                    v = [(round(v[i]), round(v[i + 1])) for i in range(0, len(v), 3)]
                    t = self.mesh.m_UV0
                    t = [(t[i] * w, t[i + 1] * h) for i in range(0, len(t), 2)]
                    f = self.mesh.m_Indices
                    for i in range(0, len(f), 6):
                        x1, y1 = v[f[i]]
                        x2, y2 = v[f[i + 3]]
                        if x1 != x2 and y1 != y2:
                            pos = (x1, y1, x2, y2)
                            quad = (*t[f[i]], *t[f[i + 1]], *t[f[i + 3]], *t[f[i + 4]])
                            val += [(pos, quad)]
                setattr(self, "_mesh", val)
        return getattr(self, "_mesh")

    @property
    def tex(self) -> Image.Image:
        if not hasattr(self, "_tex"):
            img = self.texture2D.image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            setattr(self, "_tex", img)
        return getattr(self, "_tex")

    @property
    def meshSize(self) -> Vector2:
        if not hasattr(self, "_mesh_size"):
            if self.buffer is None:
                setattr(self, "_mesh_size", None)
            else:
                v = [x[0] for x in self.buffer]
                w = max([x[2] for x in v])
                h = max([x[3] for x in v])
                setattr(self, "_mesh_size", Vector2(w, h))
        return getattr(self, "_mesh_size")

    @property
    def spriteSize(self) -> Vector2:
        return self.meshSize if self.rawSpriteSize is None else self.rawSpriteSize

    def prefered(self, layers: dict[str, Self]) -> Self:
        expands = [x for x in layers.values() if self in x and x.name != "face"]
        return sorted(expands, key=lambda v: v.sizeDelta.prod())[0]

    def decode(self) -> Image.Image:
        if not hasattr(self, "_dec_tex"):
            size = self.spriteSize.round().tuple()
            dec = self.tex.transform(size, Image.MESH, self.buffer, Image.Resampling.BICUBIC)
            setattr(self, "_dec_tex", dec)
        return getattr(self, "_dec_tex")

    def box(self, size: Optional[Vector2] = None) -> tuple[float, float, float, float]:
        x, y = self.posBiased
        w, h = self.sizeDelta if size is None else size
        return x, y, x + w, y + h

    def crop(self, img: Image.Image, resize: bool = True) -> Image.Image:
        if resize:
            return img.crop(self.box()).resize(self.spriteSize.round().tuple(), Image.Resampling.BICUBIC)
        else:
            return img.crop(self.box(self.meshSize))

    def load(self, path: str) -> bool:
        name, _ = os.path.splitext(os.path.basename(path))
        if self.name != name:
            return False
        self.repl = self.crop(open_and_transpose(path))
        logger.attr("Painting", f"'{QDir.toNativeSeparators(path)}'")
        return True


class BaseLayer:
    def __init__(self, tex2d: Texture2D, path: str):
        self.orig = tex2d.image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        self.name = tex2d.name
        self.path = path
        self.full: Image.Image = None
        self.repl: Image.Image = None

    def decode(self):
        return self.orig


class FaceLayer(BaseLayer):
    def set_data(self, layer: Layer, prefered: Layer, adv_mode: bool, is_clip: bool):
        self.layer = layer
        self.prefered = prefered
        self.adv_mode = adv_mode
        self.is_clip = is_clip

    def load_face(self, path: str):
        self.full = open_and_transpose(path)
        self.repl = self.crop_face()
        logger.attr("Paintingface", f"'{QDir.toNativeSeparators(path)}'")

    def update_clip(self, is_clip: bool):
        self.is_clip = is_clip
        if self.full is not None:
            self.repl = self.crop_face()

    def crop_face(self):
        img = self.full
        if self.adv_mode:
            if self.is_clip:
                x1, y1, x2, y2 = self.layer.box()
                rgb = Image.new("RGBA", img.size)
                rgb.paste(img.crop((x1, y1, x2 + 1, y2 + 1)), (round(x1), round(y1)))
                a = Image.new("RGBA", img.size)
                a.paste(img.crop((x1 + 1, y1 + 1, x2, y2)), (round(x1 + 1), round(y1 + 1)))
                img = Image.merge("RGBA", [*rgb.split()[:3], a.split()[-1]])
            return img.crop(self.prefered.box())
        else:
            return img.crop(self.layer.box())


class IconLayer(BaseLayer):
    def set_data(self, layer: Layer, prefered: Layer):
        self.layer = layer
        self.prefered = prefered

    def load_icon(self, path: str, preset: IconPreset) -> bool:
        name, _ = os.path.splitext(os.path.basename(path))
        if name not in ["shipyardicon", "squareicon", "herohrzicon"]:
            return False
        self.repl = open_and_transpose(path).resize(preset.tex2d.tuple(), Image.Resampling.BICUBIC)
        logger.attr("Icon", f"'{QDir.toNativeSeparators(path)}'")
        return True
