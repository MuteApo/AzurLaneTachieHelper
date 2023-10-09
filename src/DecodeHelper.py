import os
from math import ceil, floor

import numpy as np
from PIL import Image
from pytoshop.enums import ColorMode
from pytoshop.user import nested_layers
from tqdm import tqdm

from .Data import MetaInfo
from .Layer import Layer,PseudoLayer
from .Vector import Vector2


def ps_layer(
    size: Vector2, name: str, img: Image.Image, x: int, y: int, visible: bool
) -> nested_layers.Layer:
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
        name=name,
        visible=visible,
        top=size.Y - y - h,
        left=x,
        bottom=size.Y - y,
        right=x + w,
        channels=channels,
    )
    return layer


class DecodeHelper:
    @staticmethod
    def exec(
        dir: str,
        meta: MetaInfo,
        layers: dict[str, Layer],
        faces: dict[str, PseudoLayer],
        dump: bool,
    ) -> str:
        """
        Decode layers of a painting along with paintingface and return file path of the dumped psd.

        Parameters
        ----------
        dir: str
            Directory of the psd to dump on.
        meta: MetaInfo
            Metadata of the painting, including path, name, size, bias and etc.
        layers: dict[str, Layer]
            A dict containing each of the painting layers.
        faces: dict[str, PseudoLayer]
            A dict containing each of the paintingface images, as pseudo-layers.
        dump: bool
            Whether to dump intermediate layers, before assembled together as a whole psd.

        Returns
        -------
        path: str
            Path to the resulting psd.
        """

        print("[INFO] Decoding paintingface")
        face = []
        for k, v in tqdm(sorted(faces.items(), key=lambda x: int(x[0]))):
            x, y = layers["face"].posMin + meta.bias
            sub = v.decode().transform(v.size, Image.AFFINE, (1, 0, ceil(x) - x, 0, 1, y - floor(y)))
            alias = f"face [{k}]"
            face += [ps_layer(meta.size, alias, sub, ceil(x), floor(y), False)]

        print("[INFO] Decoding painting")
        painting = []
        for k, v in tqdm(layers.items()):
            if k == "face":
                painting += [nested_layers.Group(name="paintingface", layers=face, closed=False)]
            else:
                sub = v.decode().transpose(Image.FLIP_TOP_BOTTOM)
                if dump:
                    sub.save(f"{os.path.join(dir, k)}.png")
                x, y = v.posMin + meta.bias
                sub = sub.resize(v.canvasSize.round().tuple())
                sub = sub.transform(sub.size, Image.AFFINE, (1, 0, ceil(x) - x, 0, 1, y - floor(y)))
                alias = f"{v.name} [{v.texture2D.name}]"
                painting += [ps_layer(meta.size, alias, sub, ceil(x), floor(y), True)]

        psd = nested_layers.nested_layers_to_psd(painting[::-1], color_mode=ColorMode.rgb)
        path = os.path.join(dir, meta.name + ".psd")
        with open(path, "wb") as f:
            psd.write(f)

        return path
