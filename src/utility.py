import os
from pprint import pprint

import numpy as np
import UnityPy
from PIL import Image
from pytoshop.user import nested_layers
from UnityPy.classes import RectTransform


def check_dir(*dir):
    if len(dir) > 1:
        check_dir(*dir[:-1])
    if not os.path.exists(os.path.join(*dir)):
        os.mkdir(os.path.join(*dir))


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


def read_img(filename: str, resize: tuple[int, int] = None, no_ext=False) -> Image.Image:
    if no_ext:
        filename += ".png"
    img = Image.open(filename).transpose(Image.FLIP_TOP_BOTTOM)
    return img if resize is None else resize_img(img, resize)


def save_img(img: Image.Image, filename: str, no_ext=False):
    if no_ext:
        filename += ".png"
    img.transpose(Image.FLIP_TOP_BOTTOM).save(filename)


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


def get_img_area(data):
    lb = np.round(np.stack(data, -1).min(-1)).astype(np.int32)
    ru = np.round(np.stack(data, -1).max(-1)).astype(np.int32)
    return lb, ru, ru - lb


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


def gen_ps_layer(img: Image.Image, name: str, visible: bool = True) -> nested_layers.Layer:
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
