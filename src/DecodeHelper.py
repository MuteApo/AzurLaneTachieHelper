import os
from math import ceil, floor

import numpy as np
from PIL import Image, ImageOps
from pytoshop import PsdFile
from pytoshop.enums import ColorMode
from pytoshop.user import nested_layers
from tqdm import tqdm

from .Layer import FaceLayer, Layer
from .Vector import Vector2


def ps_layer(size: Vector2, name: str, img: Image.Image, x: int, y: int, visible: bool) -> nested_layers.Layer:
    """
    Generate a single psd layer.

    Parameters
    ----------
    size: str
        Width and height of the canvas.
    name: str
        Name of the psd layer.
    img: Image.Image
        A Pillow Image to put on.
    x: int
        Horizonal position.
    y: int
        Vertical position.
    visible: bool
        Whether initialized as visible.

    Returns
    -------
    layer: nested_layers.Image
        A psd layer satisfying settings given above.
    """

    w, h = img.size
    r, g, b, a = img.split()
    channels = {i - 1: np.array(x) for i, x in enumerate([a, r, g, b])}
    layer = nested_layers.Image(
        name=name, visible=visible, top=size.Y - y - h, left=x, bottom=size.Y - y, right=x + w, channels=channels
    )
    return layer


class DecodeHelper:
    @staticmethod
    def exec(dir: str, layers: dict[str, Layer], faces: dict[str, FaceLayer], is_dump: bool) -> PsdFile:
        """
        Decode layers of a painting along with paintingface and return file path of the dumped psd.

        Parameters
        ----------
        dir: str
            Directory of the psd to dump on.
        layers: dict[str, Layer]
            A dict containing each of the painting layers.
        faces: dict[int, FaceLayer]
            A dict containing each of the paintingface images, as pseudo-layers.
        is_dump: bool
            Whether to dump intermediate layers, before assembled together as a whole psd.

        Returns
        -------
        psd: PsdFile
            The resulting photoshop document.
        """

        face = []
        for k, v in tqdm(sorted(faces.items()), "[INFO] Decoding paintingface"):
            tex = v.decode().transpose(Image.FLIP_TOP_BOTTOM)
            x, y = layers["face"].posMin + layers["face"].meta.bias
            alias = f"face [{k}]"
            face += [ps_layer(layers["face"].meta.size, alias, tex, round(x), round(y), False)]

        painting = []
        for k, v in tqdm(layers.items(), "[INFO] Decoding painting"):
            if k == "face":
                painting += [nested_layers.Group(name="paintingface", layers=face, closed=False)]
            else:
                tex = v.decode().transpose(Image.FLIP_TOP_BOTTOM)
                if is_dump:
                    tex.save(f"{os.path.join(dir, k)}.png")
                tex = ImageOps.contain(tex, v.canvasSize.round().tuple())
                x, y = v.posMin + v.meta.bias
                alias = f"{v.name} [{v.texture2D.name}]"
                painting += [ps_layer(v.meta.size, alias, tex, round(x), round(y), True)]

        return nested_layers.nested_layers_to_psd(painting[::-1], color_mode=ColorMode.rgb)
