import os
from functools import cached_property
from math import ceil, floor
from typing import Callable, Literal, Optional, Self

from PIL import Image, ImageOps
from PySide6.QtCore import QDir
from UnityPy.classes import GameObject, Mesh, MonoBehaviour, PPtr, RectTransform, Sprite, Texture2D
from UnityPy.enums import ClassIDType
from UnityPy.helpers.MeshHelper import MeshHandler

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
        self.meta: MetaInfo = None
        self.modified: bool = False
        self.repl: Image.Image = None

    def __repr__(self) -> str:
        return f"Layer@{self.depth} {self.name}"

    def __str__(self) -> str:
        items = [""]
        if self.texture2D is not None:
            items += [f"Texture2D: <Texture2D name={self.texture2D.m_Name}>"]
        if self.mesh is not None:
            items += [f"Mesh: <Mesh name={self.mesh.m_Name}>"]
        attrs = ["sizeDelta", "meshSize", "rawSpriteSize"]
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
            name = self.sprite.m_Name if self.name in ["part"] else self.name
            res[name] = self
        for x in self.child:
            res |= x.flatten()
        return res

    @cached_property
    def name(self) -> str:
        return self.gameObject.m_Name if self.gameObject is not None else "Undefined"

    @cached_property
    def pathId(self) -> int:
        return self.rt.object_reader.path_id

    @cached_property
    def gameObject(self) -> GameObject:
        return self.rt.m_GameObject.read()

    @cached_property
    def monoBehaviour(self) -> Optional[MonoBehaviour]:
        for x in self.gameObject.m_Component:
            if x.component.type == ClassIDType.MonoBehaviour:
                return x.component.read()
        return None

    @cached_property
    def sprite(self) -> Optional[Sprite]:
        if self.monoBehaviour is None or not hasattr(self.monoBehaviour, "m_Sprite"):
            return None
        sprite: PPtr = self.monoBehaviour.m_Sprite
        return sprite.read() if sprite.m_PathID != 0 else None

    @cached_property
    def texture2D(self) -> Optional[Texture2D]:
        if self.sprite is None:
            return None
        return self.sprite.m_RD.texture.read()

    @cached_property
    def mesh(self) -> Optional[Mesh]:
        if self.monoBehaviour is None or not hasattr(self.monoBehaviour, "mMesh"):
            return None
        mesh: PPtr = self.monoBehaviour.mMesh
        return mesh.read() if mesh.m_PathID != 0 else None

    @cached_property
    def rawSpriteSize(self) -> Optional[Vector2]:
        if self.monoBehaviour is None or not hasattr(self.monoBehaviour, "mRawSpriteSize"):
            return None
        x = getattr(self.monoBehaviour, "mRawSpriteSize")
        return Vector2(x.x, x.y)

    @cached_property
    def anchorMin(self) -> Vector2:
        val: Vector2 = self.rt.m_AnchorMin
        return Vector2(val.x, val.y)

    @cached_property
    def anchorMax(self) -> Vector2:
        val: Vector2 = self.rt.m_AnchorMax
        return Vector2(val.x, val.y)

    @cached_property
    def anchoredPosition(self) -> Vector2:
        val: Vector2 = self.rt.m_AnchoredPosition
        return Vector2(val.x, val.y)

    @cached_property
    def sizeDelta(self) -> Vector2:
        val: Vector2 = self.rt.m_SizeDelta
        return Vector2(val.x, val.y)

    @cached_property
    def pivot(self) -> Vector2:
        val: Vector2 = self.rt.m_Pivot
        return Vector2(val.x, val.y)

    @cached_property
    def size(self) -> Vector2:
        val = self.sizeDelta
        if self.parent is not None:
            val += self.parent.sizeDelta * (self.anchorMax - self.anchorMin)
        return val

    @cached_property
    def anchorPosition(self) -> Vector2:
        if self.parent is None:
            return Vector2(0)
        anchorMin = self.parent.size * self.anchorMin
        anchorMax = self.parent.size * self.anchorMax
        return self.parent.posMin + anchorMin * (1 - self.pivot) + anchorMax * self.pivot

    @cached_property
    def pivotPosition(self) -> Vector2:
        return self.anchorPosition + self.anchoredPosition

    @cached_property
    def posMin(self) -> Vector2:
        return self.pivotPosition - self.size * self.pivot

    @cached_property
    def posMax(self) -> Vector2:
        return self.posMin + self.size

    @cached_property
    def posBiased(self) -> Vector2:
        return self.posMin + self.meta.bias

    @cached_property
    def buffer(self) -> list[tuple]:
        if self.texture2D is None:
            return None
        w, h = self.texture2D.image.size
        val = []
        if self.mesh is None:
            val += [((0, 0, w, h), (0, 0, 0, h, w, h, w, 0))]
        else:
            handler = MeshHandler(self.mesh)
            handler.process()
            v = [(round(x), round(y)) for x, y, z in handler.m_Vertices]
            t = [(u * w, v * h) for u, v in handler.m_UV0]
            f = handler.m_IndexBuffer
            for i in range(0, len(f), 6):
                x1, y1 = v[f[i]]
                x2, y2 = v[f[i + 3]]
                if x1 != x2 and y1 != y2:
                    pos = (x1, y1, x2, y2)
                    quad = (*t[f[i]], *t[f[i + 1]], *t[f[i + 3]], *t[f[i + 4]])
                    val += [(pos, quad)]
        return val

    @cached_property
    def tex(self) -> Image.Image:
        img = self.texture2D.image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        return img

    @cached_property
    def meshSize(self) -> Vector2:
        if self.buffer is None:
            return None
        v = [x[0] for x in self.buffer]
        w = max([x[2] for x in v])
        h = max([x[3] for x in v])
        return Vector2(w, h)

    @cached_property
    def spriteSize(self) -> Vector2:
        if self.rawSpriteSize is not None and self.rawSpriteSize.prod() > self.meshSize.prod():
            return self.rawSpriteSize
        return self.meshSize

    @cached_property
    def maxSize(self) -> Vector2:
        return self.spriteSize if self.spriteSize.prod() > self.sizeDelta.prod() else self.sizeDelta

    @cached_property
    def decode(self) -> Image.Image:
        size = self.spriteSize.round().tuple()
        dec = self.tex.transform(size, Image.Transform.MESH, self.buffer, Image.Resampling.BICUBIC)
        return ImageOps.contain(dec, self.maxSize.round())

    def box(self, size: Optional[Vector2] = None) -> tuple[int, int, int, int]:
        x, y = self.posBiased
        w, h = self.sizeDelta if size is None else size
        return floor(x), ceil(y), floor(x + w), ceil(y + h)

    def crop(self, img: Image.Image) -> Image.Image:
        return img.crop(self.box(self.maxSize)).resize(self.spriteSize.round(), Image.Resampling.BICUBIC)

    def load(self, path: str) -> bool:
        name, _ = os.path.splitext(os.path.basename(path))
        if self.name != name:
            return False
        self.modified = True
        self.repl = self.crop(open_and_transpose(path))
        logger.attr("Painting", f"'{QDir.toNativeSeparators(path)}'")
        return True


def prefered_layer(layers: dict[str, Layer], layer: Layer, reverse: bool = False) -> Layer:
    expands = [x for x in layers.values() if layer in x and x.name != "face"]
    return sorted(expands, key=lambda v: v.maxSize.prod())[-1 if reverse else 0]


class BaseLayer:
    def __init__(self, tex2d: Texture2D, path: str):
        self.orig = tex2d.image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        self.name = tex2d.m_Name
        self.path = path
        self.modified: bool = False
        self.full: Image.Image = None
        self.repl: Image.Image = None

    @cached_property
    def decode(self) -> Image.Image:
        return self.orig


class FaceLayer(BaseLayer):
    def set_data(
        self,
        layer: Layer,
        prefered: Callable[[Optional[bool]], Layer],
        adv_mode: Literal["off", "adaptive", "max"],
        is_clip: bool,
    ):
        self.layer = layer
        self.prefered = prefered
        self.adv_mode = adv_mode
        self.is_clip = is_clip

    def load_face(self, path: str):
        self.modified = True
        self.full = open_and_transpose(path)
        self.repl = self.crop_face()
        logger.attr("Paintingface", f"'{QDir.toNativeSeparators(path)}'")

    def update_clip(self, is_clip: bool):
        self.is_clip = is_clip
        if self.full is not None:
            self.repl = self.crop_face()

    def crop_face(self):
        prefered = self.prefered(self.adv_mode == "max")
        print(prefered)
        img = self.full
        if self.adv_mode == "off":
            return img.crop(self.layer.box())
        else:
            if self.is_clip:
                x1, y1, x2, y2 = self.layer.box(prefered.maxSize if self.adv_mode == "max" else None)
                rgb = Image.new("RGBA", img.size)
                rgb.paste(img.crop((x1, y1, x2 + 1, y2 + 1)), (x1, y1))
                a = Image.new("RGBA", img.size)
                a.paste(img.crop((x1 + 1, y1 + 1, x2, y2)), (x1 + 1, y1 + 1))
                img = Image.merge("RGBA", [*rgb.split()[:3], a.split()[-1]])
            return img.crop(prefered.box())


class IconLayer(BaseLayer):
    def set_data(self, layer: Layer, prefered: Layer):
        self.layer = layer
        self.prefered = prefered

    def load_icon(self, path: str, preset: IconPreset) -> bool:
        name, _ = os.path.splitext(os.path.basename(path))
        if name not in ["shipyardicon", "herohrzicon", "squareicon"]:
            return False
        self.modified = True
        self.repl = open_and_transpose(path).resize(preset.tex2d, Image.Resampling.BICUBIC)
        logger.attr("Icon", f"'{QDir.toNativeSeparators(path)}'")
        return True
