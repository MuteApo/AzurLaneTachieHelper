import os

from PIL import Image


def check_and_save(path: str, data: bytes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def open_and_transpose(path: str) -> Image.Image:
    return Image.open(path).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
