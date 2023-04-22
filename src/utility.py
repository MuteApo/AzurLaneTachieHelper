import os
from pprint import pprint

import numpy as np
import UnityPy
from PIL import Image
from pytoshop.user import nested_layers
from UnityPy import Environment
from UnityPy.classes import RectTransform


def check_dir(*dir):
    if len(dir) > 1:
        check_dir(*dir[:-1])
    if not os.path.exists(os.path.join(*dir)):
        os.mkdir(os.path.join(*dir))


def filter_typename(env: Environment, typename: str):
    return [_.read() for _ in env.objects if _.type.name == typename]


def parse_obj(mesh: str):
    name = mesh + ".obj"
    with open(name) as file:
        lines = [_.replace("\n", "").split(" ") for _ in file.readlines()]

        data = {
            "g": [],  # group name
            "v": [],  # geometric vertices
            "vt": [],  # texture vertices
            "f": [],  # face, indexed as v/vt/vn
        }
        for line in lines:
            data[line[0]].append(line[1:])

        v = np.array(data["v"], dtype=np.float32)
        vt = np.array(data["vt"], dtype=np.float32)
        f = np.array(
            [[[___ for ___ in __.split("/")] for __ in _] for _ in data["f"]],
            dtype=np.int32,
        )

        v[:, 0] = -v[:, 0]
        s = np.stack(v, -1).max(-1) + 1

        print(f"[INFO] Mesh file: {name}")
        print(f"[INFO] Vertex count: {len(v)}")
        print(f"[INFO] Texcoord count: {len(vt)}")
        print(f"[INFO] Face count: {len(f)}")
        print(f"[INFO] Mesh size: {s[:2]}")

    return {"v": v, "vt": vt, "f": f, "v_normalized": v / s}


def resize_img(
    img: Image.Image,
    size: tuple[int, int],
    resample: Image.Resampling = Image.Resampling.LANCZOS,
) -> Image.Image:
    return img.resize(size, resample=resample)


def scale_img(
    img: Image.Image,
    scale: float,
    resample: Image.Resampling = Image.Resampling.LANCZOS,
) -> Image.Image:
    w, h = img.size
    size = np.round([w * scale, h * scale]).astype(np.int32)
    return img.resize(size, resample=resample)


def read_img(filename: str, resize: tuple[int, int] = None) -> Image.Image:
    img = Image.open(filename + ".png").transpose(Image.FLIP_TOP_BOTTOM)
    return img if resize is None else resize_img(img, resize)


def save_img(img: Image.Image, filename: str):
    img.transpose(Image.FLIP_TOP_BOTTOM).save(filename + ".png")


def get_rt_name(rect: RectTransform) -> str:
    return rect.m_GameObject.read().m_Name


def convert(rect: RectTransform) -> dict[str, np.ndarray]:
    entry = [
        "m_LocalPosition",
        "m_LocalScale",
        "m_AnchorMin",
        "m_AnchorMax",
        "m_AnchoredPosition",
        "m_SizeDelta",
        "m_Pivot",
    ]
    return {_: np.array([*rect.to_dict()[_].values()][:2]) for _ in entry}


def clip_box(offset: np.ndarray, size: np.ndarray, bound: np.ndarray):
    x, y = np.maximum(np.round(offset), 0).astype(np.int32)
    w, h = np.minimum(size + [x, y], bound).astype(np.int32) - [x, y]
    return x, y, w, h


def get_img_area(data, size, pad=0):
    bound = np.array(size) - 1

    # pad with one extra pixel and clip
    lb = np.round(np.maximum(np.stack(data, -1).min(-1) - pad, 0)).astype(np.int32)
    ru = np.round(np.minimum(np.stack(data, -1).max(-1) + pad, bound)).astype(np.int32)

    return *lb, *(ru - lb + 1)


def decode_tex(
    enc_img: Image.Image,
    dec_size: tuple[int, int],
    v: np.ndarray,
    vt: np.ndarray,
    f: np.ndarray,
    **_,
) -> Image.Image:
    dec_img = Image.new("RGBA", dec_size)
    enc_size = np.array(enc_img.size)

    for rect in zip(f[::2], f[1::2]):
        index_v, index_vt = np.stack([*rect[0][:2, :2], *rect[1][:2, :2]], -1)

        x1, y1, w1, h1 = get_img_area(v[index_v - 1, :2], dec_size, 0)
        x2, y2, w2, h2 = get_img_area(vt[index_vt - 1] * enc_size, enc_size, 0)
        # print(x1, y1, w1, h1)
        # print(x2, y2, w2, h2)

        sub = enc_img.crop((x2, y2, x2 + w2, y2 + h2)).resize((w1, h1))
        dec_img.paste(sub, (x1, y1))

    return dec_img


def encode_tex(
    dec_img: Image.Image,
    enc_size: tuple[int, int],
    v: np.ndarray,
    vt: np.ndarray,
    f: np.ndarray,
    **_,
):
    enc_img = Image.new("RGBA", enc_size)
    dec_size = np.array(dec_img.size)

    for rect in zip(f[::2], f[1::2]):
        index_v, index_vt = np.stack([*rect[0][:2, :2], *rect[1][:2, :2]], -1)

        x1, y1, w1, h1 = get_img_area(v[index_v - 1, :2], dec_size, 1)
        x2, y2, w2, h2 = get_img_area(vt[index_vt - 1] * enc_size, enc_size, 1)
        # print(x1, y1, w1, h1)
        # print(x2, y2, w2, h2)

        sub = dec_img.crop((x1, y1, x1 + w1, y1 + h1)).resize((w2, h2))
        enc_img.paste(sub, (x2, y2))

    return enc_img


def get_rect_transform(filename):
    assets = UnityPy.load(filename)
    game_objects = [_.read() for _ in assets.objects if _.type.name == "GameObject"]
    face_gameobj = [_ for _ in game_objects if _.m_Name == "face"][0]
    face_rect = face_gameobj.read().m_Component[0].component.read()
    base_rect = face_rect.read().m_Father.read()

    print("[INFO] Face GameObject PathID:", face_gameobj.path_id)
    print("[INFO] Face RectTransform PathID:", face_rect.path_id)
    print("[INFO] Base RectTransform PathID:", base_rect.path_id)

    base = convert(base_rect)
    face = convert(face_rect)

    print("[INFO] Face RectTransform data:")
    pprint(base)
    print("[INFO] Base RectTransform data:")
    pprint(face)

    base_pivot = base["m_SizeDelta"] * base["m_Pivot"]
    face_pivot = base_pivot + face["m_LocalPosition"][:2]
    face_offset = face_pivot - face["m_SizeDelta"] * face["m_Pivot"]

    x, y = np.round(face_offset).astype(np.int32)
    w, h = face["m_SizeDelta"].astype(np.int32)

    print("[INFO] Paintingface area:", x, y, w, h)

    return base, face, x, y, w, h


def gen_ps_layer(
    img: Image.Image, name: str, visible: bool = True
) -> nested_layers.Layer:
    r, g, b, a = img.transpose(Image.FLIP_TOP_BOTTOM).split()
    channels = {i - 1: np.array(x) for i, x in enumerate([a, r, g, b])}
    w, h = img.size
    layer = nested_layers.Image(
        name=name,
        visible=visible,
        opacity=255,
        top=0,
        left=0,
        bottom=h,
        right=w,
        channels=channels,
    )
    return layer
