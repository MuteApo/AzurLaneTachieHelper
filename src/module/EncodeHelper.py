import os
import struct

import UnityPy
from PIL import Image
from tqdm import tqdm
from UnityPy.classes import Sprite, Texture2D
from UnityPy.enums import ClassIDType, TextureFormat

from ..base import FaceLayer, IconLayer, Layer
from ..utility import check_dir


def set_sprite(sprite: Sprite, img: Image.Image):
    sprite.m_Rect.width, sprite.m_Rect.height = img.size
    sprite.m_RD.textureRect.width, sprite.m_RD.textureRect.height = img.size
    sprite.save()


def set_tex2d(tex2d: Texture2D, img: Image.Image):
    tex2d.m_Width, tex2d.m_Height = img.size
    tex2d.set_image(img.transpose(Image.FLIP_TOP_BOTTOM), TextureFormat.RGBA32)
    tex2d.save()


def replace_painting(dir: str, layer: Layer) -> str:
    path = layer.path if layer.path != "Not Found" else layer.meta.path
    env = UnityPy.load(path)

    for x in env.objects:
        if x.type == ClassIDType.Texture2D:
            set_tex2d(x.read(), layer.repl)
        elif x.type == ClassIDType.Mesh:
            mesh = x.read_typetree()

            mesh["m_SubMeshes"][0]["indexCount"] = 6
            mesh["m_SubMeshes"][0]["vertexCount"] = 4
            mesh["m_IndexBuffer"] = [0, 0, 1, 0, 2, 0, 2, 0, 3, 0, 0, 0]
            mesh["m_VertexData"]["m_VertexCount"] = 4
            w, h = layer.repl.size
            buf = [0, 0, 0, 0, 0, 0, h, 0, 0, 1, w, h, 0, 1, 1, w, 0, 0, 1, 0]
            data_size = struct.pack(x.reader.endian + "f" * 20, *buf)
            mesh["m_VertexData"]["m_DataSize"] = memoryview(data_size)

            x.save_typetree(mesh)

    check_dir(dir, "output", "painting")
    output = os.path.join(dir, "output", "painting", os.path.basename(path))
    with open(output, "wb") as f:
        f.write(env.file.save("original"))

    return output


def replace_meta(dir: str, layer: Layer, prefered: Layer) -> str:
    env = UnityPy.load(layer.meta.path)
    cab = list(env.cabs.values())[0]
    face_rt = cab.objects[layer.pathId]
    face = face_rt.read_typetree()
    w, h = prefered.sizeDelta
    px, py = prefered.pivot
    x1, y1 = prefered.posPivot - layer.parent.posPivot
    x2, y2 = prefered.posPivot - layer.posAnchor + layer.meta.bias
    face["m_SizeDelta"] = {"x": w, "y": h}
    face["m_Pivot"] = {"x": px, "y": py}
    face["m_LocalPosition"] = {"x": x1, "y": y1, "z": 0.0}
    face["m_AnchoredPosition"] = {"x": x2, "y": y2}
    face_rt.save_typetree(face)

    check_dir(dir, "output", "painting")
    path = os.path.join(dir, "output", "painting", os.path.basename(layer.meta.path))
    with open(path, "wb") as f:
        f.write(env.file.save("original"))

    return [path]


def replace_face(dir: str, faces: dict[str, FaceLayer]) -> list[str]:
    first = list(faces.values())[0]
    layer = first.layer
    prefered = first.prefered
    adv_mode = first.adv_mode

    base = layer.meta.name_stem
    path = os.path.join(os.path.dirname(layer.meta.path), "paintingface", base)
    env = UnityPy.load(path)

    sprites: list[Sprite] = [x.read() for x in env.objects if x.type == ClassIDType.Sprite]
    for sprite in tqdm(filter(lambda x: x.name in faces, sprites), "[INFO] Encoding paintingface"):
        img = faces[sprite.name].repl
        set_sprite(sprite, img)
        set_tex2d(sprite.m_RD.texture.read(), img)

    check_dir(dir, "output", "paintingface")
    output = os.path.join(dir, "output", "paintingface", base)
    with open(output, "wb") as f:
        f.write(env.file.save("original"))

    if adv_mode:
        return replace_meta(dir, layer, prefered) + [output]
    else:
        return [output]


def replace_icon(dir: str, kind: str, icon: IconLayer):
    env = UnityPy.load(icon.path)
    for v in env.container.values():
        set_tex2d(v.read().m_RD.texture.read(), icon.repl)

    check_dir(dir, "output", kind)
    outdir = os.path.join(dir, "output", kind)
    path = os.path.join(outdir, icon.layer.meta.name_stem)
    with open(path, "wb") as f:
        f.write(env.file.save("original"))

    return path


class EncodeHelper:
    @staticmethod
    def exec(dir: str, layers: dict[str, Layer], faces: dict[str, FaceLayer], icons: dict[str, IconLayer]) -> list[str]:
        result = []

        valid = [v for v in layers.values() if v.repl is not None]
        if valid != []:
            result += [replace_painting(dir, x) for x in tqdm(valid, "[INFO] Encoding painting")]

        valid = {k: v for k, v in faces.items() if v.repl is not None}
        if valid != {}:
            result += replace_face(dir, valid)

        valid = {k: v for k, v in icons.items() if v.repl is not None and os.path.exists(v.path)}
        if valid != {}:
            result += [replace_icon(dir, k, v) for k, v in tqdm(valid.items(), "[INFO] Encoding icons")]

        return result
