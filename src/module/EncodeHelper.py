import os
import struct

import UnityPy
from PIL import Image
from tqdm import tqdm
from UnityPy.classes import Mesh, RectTransform, Sprite, Texture2D
from UnityPy.enums import ClassIDType, TextureFormat

from ..base import FaceLayer, IconLayer, Layer
from ..utility import check_and_save


def set_tex2d(tex2d: Texture2D, img: Image.Image):
    tex2d.m_Width, tex2d.m_Height = img.size
    tex2d.set_image(img.transpose(Image.Transpose.FLIP_TOP_BOTTOM), TextureFormat.RGBA32)
    tex2d.save()


def set_mesh(mesh: Mesh, img: Image.Image):
    data = mesh.read_typetree()

    data["m_SubMeshes"][0]["indexCount"] = 6
    data["m_SubMeshes"][0]["vertexCount"] = 4
    data["m_IndexBuffer"] = [0, 0, 1, 0, 2, 0, 2, 0, 3, 0, 0, 0]
    data["m_VertexData"]["m_VertexCount"] = 4

    w, h = img.size
    buf = [0, 0, 0, 0, 0, 0, h, 0, 0, 1, w, h, 0, 1, 1, w, 0, 0, 1, 0]
    data_size = struct.pack(mesh.reader.endian + "f" * 20, *buf)
    data["m_VertexData"]["m_DataSize"] = memoryview(data_size)

    mesh.save_typetree(data)


def replace_painting(dir: str, layer: Layer) -> str:
    path = layer.path if layer.path != "Not Found" else layer.meta.path
    env = UnityPy.load(path)

    for x in env.objects:
        if x.type == ClassIDType.Texture2D:
            set_tex2d(x.read(), layer.repl)
        elif x.type == ClassIDType.Mesh:
            set_mesh(x, layer.repl)

    path = os.path.join(dir, "output", "painting", os.path.basename(path))
    check_and_save(path, env.file.save("original"))

    return path


def replace_meta(dir: str, layer: Layer, prefered: Layer) -> str:
    env = UnityPy.load(layer.meta.path)
    cab = list(env.cabs.values())[0]
    face_rt: RectTransform = cab.objects[layer.pathId]
    data = face_rt.read_typetree()
    w, h = prefered.sizeDelta
    data["m_SizeDelta"] = {"x": w, "y": h}
    px, py = prefered.pivot
    data["m_Pivot"] = {"x": px, "y": py}
    x, y = prefered.pivotPosition - layer.anchorPosition + layer.meta.bias
    data["m_AnchoredPosition"] = {"x": x, "y": y}
    face_rt.save_typetree(data)

    path = os.path.join(dir, "output", "painting", os.path.basename(layer.meta.path))
    check_and_save(path, env.file.save("original"))

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
    for sprite in tqdm(filter(lambda x: x.name in faces, sprites), "Encode paintingface"):
        img = faces[sprite.name].repl
        set_tex2d(sprite.m_RD.texture.read(), img)

    path = os.path.join(dir, "output", "paintingface", base)
    check_and_save(path, env.file.save("original"))

    if adv_mode:
        return replace_meta(dir, layer, prefered) + [path]
    else:
        return [path]


def replace_icon(dir: str, kind: str, icon: IconLayer):
    env = UnityPy.load(icon.path)
    for v in env.container.values():
        set_tex2d(v.read().m_RD.texture.read(), icon.repl)

    path = os.path.join(dir, "output", kind, icon.layer.meta.name_stem)
    check_and_save(path, env.file.save("original"))

    return path


class EncodeHelper:
    @staticmethod
    def exec(dir: str, layers: dict[str, Layer], faces: dict[str, FaceLayer], icons: dict[str, IconLayer]) -> list[str]:
        result = []

        valid = [v for v in layers.values() if v.repl is not None]
        if valid != []:
            result += [replace_painting(dir, x) for x in tqdm(valid, "Encode painting")]

        valid = {k: v for k, v in faces.items() if v.repl is not None}
        if valid != {}:
            result += replace_face(dir, valid)

        valid = {k: v for k, v in icons.items() if v.repl is not None and os.path.exists(v.path)}
        if valid != {}:
            result += [replace_icon(dir, k, v) for k, v in tqdm(valid.items(), "Encode icons")]

        return result
