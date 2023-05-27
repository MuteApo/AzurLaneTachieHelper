import os
import re

from PIL import Image
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
