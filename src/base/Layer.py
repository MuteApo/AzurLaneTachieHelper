from functools import cached_property
from typing import Callable, Optional, Self

from PIL import Image, ImageOps
from PySide6.QtCore import QDir
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
from UnityPy.helpers.MeshHelper import MeshHandler

from ..logger import logger
from ..utility import open_and_transpose
from . import Config
from .Data import FaceModeType, MetaInfo
from .Vector import Vector2


class Layer:
    def __init__(self, rt: PPtr[RectTransform], parent: Self = None):
        self.rt = rt.read()
        self.parent = parent
        self.depth = 1 if parent is None else parent.depth + 1
        self.child = [Layer(x, self) for x in self.rt.m_Children]
        self.path: str = "Not Found"
        self.meta: MetaInfo = None
        self.modified: bool = False
        self.full: Image.Image = None
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

    def traverse(self, func: Callable[[Self], None]):
        func(self)
        for x in self.child:
            x.traverse(func)

    def flatten(self) -> dict[str, Self]:
        res = {}
        if self.sprite is not None:
            res[self.validName] = self
        for x in self.child:
            res |= x.flatten()
        return res

    def access_with_fallback(self, name: str):
        if hasattr(self.rt, name):
            return getattr(self.rt, name)
        return getattr(self.parent.rt, name)

    @cached_property
    def name(self) -> str:
        return self.gameObject.m_Name if self.gameObject is not None else "Undefined"
    
    @cached_property
    def validName(self) -> str:
        return self.sprite.m_Name if self.name in ["part"] else self.name

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
        return Vector2(self.monoBehaviour.mRawSpriteSize)

    @cached_property
    def anchorMin(self) -> Vector2:
        return Vector2(self.access_with_fallback("m_AnchorMin"))

    @cached_property
    def anchorMax(self) -> Vector2:
        return Vector2(self.access_with_fallback("m_AnchorMax"))

    @cached_property
    def anchoredPosition(self) -> Vector2:
        return Vector2(self.access_with_fallback("m_AnchoredPosition"))

    @cached_property
    def sizeDelta(self) -> Vector2:
        return Vector2(self.access_with_fallback("m_SizeDelta"))

    @cached_property
    def pivot(self) -> Vector2:
        return Vector2(self.access_with_fallback("m_Pivot"))

    @cached_property
    def localPosition(self) -> Vector2:
        return Vector2(self.access_with_fallback("m_LocalPosition"))

    @cached_property
    def localScale(self) -> Vector2:
        if self.parent is None:
            return Vector2(1.0, 1.0)
        else:
            return Vector2(self.access_with_fallback("m_LocalScale"))

    @cached_property
    def accumScale(self) -> Vector2:
        if self.parent is None:
            return Vector2(1.0, 1.0)
        else:
            if isinstance(self.parent.rt, RectTransform):
                return self.parent.accumScale
            else:
                return self.parent.globalScale

    @cached_property
    def globalScale(self) -> Vector2:
        return self.accumScale * self.localScale

    @cached_property
    def unscaledSize(self) -> Vector2:
        if self.parent is None:
            if isinstance(self.rt, RectTransform):
                return self.sizeDelta
            else:
                return Vector2(0.0, 0.0)
        else:
            if isinstance(self.rt, RectTransform):
                return self.sizeDelta + (self.anchorMax - self.anchorMin) * self.parent.size
            else:
                return Vector2(0.0, 0.0)

    @cached_property
    def size(self) -> Vector2:
        return self.unscaledSize * self.globalScale

    @cached_property
    def pivotPosition(self) -> Vector2:
        if self.parent is None:
            if isinstance(self.rt, RectTransform):
                return self.size * self.pivot
            else:
                return Vector2(0.0, 0.0)
        else:
            if isinstance(self.rt, RectTransform):
                if isinstance(self.parent.rt, RectTransform):
                    offset = self.anchorMin + (self.anchorMax - self.anchorMin) * self.pivot
                    return self.parent.posMin + self.anchoredPosition * self.accumScale + self.parent.size * offset
                else:
                    return self.parent.pivotPosition + self.anchoredPosition * self.accumScale
            else:
                return self.parent.pivotPosition + self.localPosition * self.accumScale

    @cached_property
    def anchorPosition(self) -> Vector2:
        if self.parent is None:
            return Vector2(0.0, 0.0)
        anchorMin = self.parent.size * self.anchorMin
        anchorMax = self.parent.size * self.anchorMax
        return self.parent.posMin + anchorMin * (1.0 - self.pivot) + anchorMax * self.pivot

    @cached_property
    def posMin(self) -> Vector2:
        if self.parent is None:
            return Vector2(0.0, 0.0)
        else:
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

    def decode(self) -> Image.Image:
        size = self.rawSpriteSize if Config.get_mesh_mode() == 0 else self.meshSize
        dec = self.tex.transform(size.round().tuple(), Image.Transform.MESH, self.buffer, Image.Resampling.BICUBIC)
        return ImageOps.contain(dec, (self.sizeDelta * self.localScale).round())

    @cached_property
    def box(self) -> tuple[int, int, int, int]:
        x, y = self.posBiased
        w, h = self.sizeDelta
        return round(x), round(y), round(x + w), round(y + h)

    def crop(self) -> Image.Image:
        if Config.get_face_mode() == FaceModeType.Custom:
            face_extension = Config.get_face_extension(self.meta.name_stem, self.validName)
            box = [a + b for a, b in zip(self.box, face_extension)]
        else:
            box = self.box
        img = self.safe_crop(self.full, box)
        if self.depth == 1:
            size = self.rawSpriteSize if Config.get_mesh_mode() == 0 else self.meshSize
            img = img.resize(size.round(), Image.Resampling.BICUBIC)
        return img

    def safe_crop(self, x: Image.Image, box: tuple[int, int, int, int]):
        w, h = x.size
        x1, y1, x2, y2 = box
        safe_box = (max(0, x1), max(0, y1), min(x2, w), min(y2, h))
        return x.crop(safe_box)

    def refresh(self):
        if self.full is not None:
            self.repl = self.crop()

    def load(self, path: str):
        logger.attr("Painting", f"'{QDir.toNativeSeparators(path)}'")
        self.modified = True
        self.full = open_and_transpose(path)
        self.refresh()


def prefered_layer(layers: dict[str, Layer], layer: Layer) -> Layer:
    expands = [x for x in layers.values() if x.name != "face"]
    return sorted(expands, key=lambda v: v.sizeDelta.prod())[0]


class BaseLayer:
    def __init__(self, meta: MetaInfo, tex2d: Texture2D, path: str):
        self.meta = meta
        self.orig = tex2d.image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        self.name = tex2d.m_Name
        self.path = path
        self.modified: bool = False
        self.full: Image.Image = None
        self.repl: Image.Image = None

    def decode(self) -> Image.Image:
        return self.orig


class FaceLayer(BaseLayer):
    def set_data(self, layer: Layer, prefered: Layer):
        self.layer = layer
        self.prefered = prefered

    def load_face(self, path: str):
        logger.attr("Paintingface", f"'{QDir.toNativeSeparators(path)}'")
        self.modified = True
        self.full = open_and_transpose(path)
        self.refresh()

    def refresh(self):
        if self.full is not None:
            self.repl = self.crop_face()

    def crop_face(self):
        face_mode = Config.get_face_mode()
        if face_mode == FaceModeType.Off:
            return self.full.crop(self.layer.box)

        if face_mode == FaceModeType.Auto:
            prefered_box = self.prefered.box
        elif face_mode == FaceModeType.Custom:
            face_extension = Config.get_face_extension(self.layer.meta.name_stem, "paintingface")
            prefered_box = [a + b for a, b in zip(self.layer.box, face_extension)]
        else:
            raise ValueError(f"Unknown face mode: {face_mode}")

        return self.safe_crop(self.full, prefered_box)

    def safe_crop(self, x: Image.Image, box: tuple[int, int, int, int]):
        w, h = x.size
        x1, y1, x2, y2 = box
        safe_box = (max(0, x1), max(0, y1), min(x2, w), min(y2, h))
        return x.crop(safe_box)


class IconLayer(BaseLayer):
    def set_data(self, layer: Layer):
        self.layer = layer

    def load_icon(self, path: str):
        logger.attr("Icon", f"'{QDir.toNativeSeparators(path)}'")
        self.modified = True
        self.repl = open_and_transpose(path).resize(self.orig.size, Image.Resampling.BICUBIC)
