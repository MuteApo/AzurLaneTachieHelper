import os

from PIL import Image


def check_dir(*dir):
    if len(dir) > 1:
        check_dir(*dir[:-1])
    path = os.path.join(*dir)
    if not os.path.exists(path):
        os.mkdir(path)

def open_and_transpose(path: str) -> Image.Image:
    return Image.open(path).transpose(Image.Transpose.FLIP_TOP_BOTTOM)