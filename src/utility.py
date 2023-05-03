import os
import re

import numpy as np
from PIL import Image
from pytoshop.user import nested_layers
from UnityPy import Environment


def raw_name(path: str) -> str:
    return re.split(r"/|_tex", path)[-2]


def check_dir(*dir):
    if len(dir) > 1:
        check_dir(*dir[:-1])
    if not os.path.exists(os.path.join(*dir)):
        os.mkdir(os.path.join(*dir))


def read_img(filename: str, resize: tuple[int, int] = None, no_ext: bool = False) -> Image.Image:
    if no_ext:
        filename += ".png"
    img = Image.open(filename).transpose(Image.FLIP_TOP_BOTTOM)
    if resize is not None:
        img = img.resize(resize, Image.Resampling.LANCZOS)
    return img


def save_img(img: Image.Image, filename: str, no_ext=False):
    if no_ext:
        filename += ".png"
    img.transpose(Image.FLIP_TOP_BOTTOM).save(filename)


def filter_env(env: Environment, type: type, read: bool = True):
    return [_.read() if read else _ for _ in env.objects if _.type.name == type.__name__]


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
