import os

import numpy as np
from PIL import Image, ImageOps
from pytoshop import PsdFile
from pytoshop.enums import ColorMode
from pytoshop.user import nested_layers
from tqdm import tqdm

from ..base import FaceLayer, Layer, Vector2


def ps_layer(name: str, pos: Vector2, size: Vector2, img: Image.Image, visible: bool) -> nested_layers.Layer:
    """
    Generate a single psd layer.

    Parameters
    ----------
    name: str
        Name of the layer.
    pos: Vector2
        Position of the image.
    size: Vector2
        Width and height of the canvas.
    img: Image.Image
        A Pillow Image to put on.
    visible: bool
        Whether initialized as visible.

    Returns
    -------
    layer: nested_layers.Image
        A psd layer satisfying settings given above.
    """

    x, y = pos
    w, h = img.size
    r, g, b, a = img.split()
    channels = {i - 1: np.array(x) for i, x in enumerate([a, r, g, b])}
    layer = nested_layers.Image(
        name=name,
        visible=visible,
        top=round(size.Y - y - h),
        left=round(x),
        bottom=round(size.Y - y),
        right=round(x + w),
        channels=channels,
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
        for k, v in tqdm(sorted(faces.items()), "Decode paintingface"):
            tex = v.decode().transpose(Image.FLIP_TOP_BOTTOM)
            face += [ps_layer(f"face #{k}", layers["face"].posBiased, layers["face"].meta.size, tex, False)]

        painting = []
        for k, v in tqdm(layers.items(), "Decode painting"):
            if k == "face":
                painting += [nested_layers.Group(name="paintingface", layers=face, closed=False)]
            else:
                tex = v.decode().transpose(Image.FLIP_TOP_BOTTOM)
                if is_dump:
                    tex.save(f"{os.path.join(dir, k)}.png")
                tex = ImageOps.contain(tex, v.sizeDelta.round())
                painting += [ps_layer(f"{v.name} [{v.texture2D.name}]", v.posBiased, v.meta.size, tex, True)]

        return nested_layers.nested_layers_to_psd(painting[::-1], color_mode=ColorMode.rgb)
