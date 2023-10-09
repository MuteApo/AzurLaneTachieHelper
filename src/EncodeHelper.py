import os
import struct

import UnityPy
from PIL import Image
from tqdm import tqdm
from UnityPy.classes import Mesh, Sprite, Texture2D
from UnityPy.enums import TextureFormat

from .Data import IconPreset, MetaInfo
from .Layer import Layer, PseudoLayer
from .utility import check_dir, filter_env


def replace_painting(dir: str, layer: Layer) -> str:
    env = UnityPy.load(layer.path)

    for _ in filter_env(env, Texture2D):
        tex2d: Texture2D = _.read()
        img = layer.repl
        tex2d.m_Width, tex2d.m_Height = img.size
        tex2d.set_image(img.transpose(Image.FLIP_TOP_BOTTOM), TextureFormat.RGBA32)
        tex2d.save()

    for _ in filter_env(env, Mesh, False):
        mesh = _.read_typetree()

        mesh["m_SubMeshes"][0]["indexCount"] = 6
        mesh["m_SubMeshes"][0]["vertexCount"] = 4
        mesh["m_IndexBuffer"] = [0, 0, 1, 0, 2, 0, 2, 0, 3, 0, 0, 0]
        mesh["m_VertexData"]["m_VertexCount"] = 4
        w, h = layer.repl.size
        buf = [0, 0, 0, 0, 0, 0, h, 0, 0, 1, w, h, 0, 1, 1, w, 0, 0, 1, 0]
        data_size = struct.pack(_.reader.endian + "f" * 20, *buf)
        mesh["m_VertexData"]["m_DataSize"] = memoryview(data_size)

        _.save_typetree(mesh)

    check_dir(dir, "output", "painting")
    output = os.path.join(dir, "output", "painting", os.path.basename(layer.path))
    with open(output, "wb") as f:
        f.write(env.file.save("original"))

    return output


def replace_meta(dir: str, layer: Layer, prefered: Layer) -> str:
    env = UnityPy.load(layer.meta.path)
    cab = list(env.cabs.values())[0]
    face_rt = cab.objects[layer.pathId]
    face = face_rt.read_typetree()
    w, h = prefered.canvasSize
    px, py = prefered.pivot
    fix = (prefered.canvasSize - prefered.sizeDelta) * prefered.pivot
    x1, y1 = prefered.posPivot - layer.parent.posPivot + fix
    x2, y2 = prefered.posPivot - layer.posAnchor + layer.meta.bias + fix
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


def replace_face(dir: str, faces: dict[str, PseudoLayer]) -> list[str]:
    first = list(faces.values())[0]
    layer = first.layer
    prefered = first.prefered
    adv_mode = first.adv_mode

    base = layer.meta.name.removesuffix("_n").lower()
    path = os.path.join(os.path.dirname(layer.meta.path), "paintingface", base)
    env = UnityPy.load(path)

    valid: list[Sprite] = [x for x in filter_env(env, Sprite) if x.name in faces]
    for sprite in tqdm(valid):
        img = faces[sprite.name].repl
        sprite.m_Rect.width, sprite.m_Rect.height = img.size
        sprite.m_RD.textureRect.width, sprite.m_RD.textureRect.height = img.size
        sprite.save()

        tex2d: Texture2D = sprite.m_RD.texture.read()
        tex2d.m_Width, tex2d.m_Height = img.size
        tex2d.set_image(img.transpose(Image.FLIP_TOP_BOTTOM), TextureFormat.RGBA32)
        tex2d.save()

    check_dir(dir, "output", "paintingface")
    output = os.path.join(dir, "output", "paintingface", base)
    with open(output, "wb") as f:
        f.write(env.file.save("original"))

    if adv_mode:
        return replace_meta(dir, layer, prefered) + [output]
    else:
        return [output]


def aspect_ratio(preset: IconPreset, w: int, h: int, clip: bool):
    std = preset.tex2d
    if clip:
        w = round(w / std.X * preset.sprite.X)
    return w, h


def replace_icon(dir: str, meta: MetaInfo, kind: str, repls: dict[str, Image.Image]):
    base = meta.name.removesuffix("_n").lower()
    path = os.path.join(os.path.dirname(meta), kind, base)
    if not os.path.exists(path):
        return

    env = UnityPy.load(path)
    preset = IconPreset.default()[kind]
    for v in env.container.values():
        img = repls[kind]
        tex2d_size = aspect_ratio(preset, *img.size, False)
        sprite_size = aspect_ratio(preset, *img.size, True)
        sub = Image.new("RGBA", tex2d_size)
        sub.paste(img.crop((0, 0, *sprite_size)))

        sprite: Sprite = v.read()
        tex2d: Texture2D = sprite.m_RD.texture.read()
        tex2d.set_image(sub.resize(tex2d.image.size), TextureFormat.RGBA32)
        tex2d.save()

    check_dir(dir, "output", kind)
    outdir = os.path.join(dir, "output", kind)
    path = os.path.join(outdir, base)
    with open(path, "wb") as f:
        f.write(env.file.save("original"))

    return path


class EncodeHelper:
    @staticmethod
    def exec(
        dir: str,
        meta: MetaInfo,
        layers: dict[str, Layer],
        faces: dict[str, PseudoLayer],
        repls: dict[str, Image.Image],
        icons: dict[str, Image.Image],
        enable_icon: bool,
    ) -> list[str]:
        painting = []
        valid = [v for v in layers.values() if v.repl is not None]
        if valid != []:
            print("[INFO] Encoding painting")
            painting += [replace_painting(dir, x) for x in tqdm(valid)]

        face = []

        valid = dict(filter(lambda x: x[1].repl is not None, faces.items()))
        if valid != {}:
            print("[INFO] Encoding paintingface")
            face += replace_face(dir, valid)

        icon = []
        valid = [k for k in icons.keys() if k in repls]
        if enable_icon and valid != []:
            print("[INFO] Encoding icons")
            icon += [replace_icon(dir, meta, x, repls) for x in tqdm(valid)]

        return painting + face + icon
