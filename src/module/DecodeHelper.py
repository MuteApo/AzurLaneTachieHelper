from math import floor

import numpy as np
from PIL import Image, ImageOps
from pytoshop import PsdFile
from pytoshop.enums import ColorMode
from pytoshop.user import nested_layers
from rich.progress import Progress

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
        top=floor(size.Y - y - h),
        left=floor(x),
        bottom=floor(size.Y - y),
        right=floor(x + w),
        channels=channels,
    )
    return layer


class DecodeHelper:
    @staticmethod
    def exec(layers: dict[str, Layer], faces: dict[str, FaceLayer]) -> PsdFile:
        """
        Decode layers of a painting along with paintingface and return file path of the dumped psd.

        Parameters
        ----------
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
        with Progress() as progress:
            task = progress.add_task("Decode paintingface", total=len(faces))
            for k, v in sorted(faces.items()):
                tex = v.decode().transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                face += [ps_layer(f"face #{k}", layers["face"].posBiased, layers["face"].meta.size, tex, False)]
                progress.update(task, advance=1)

        painting = []
        with Progress() as progress:
            task = progress.add_task("Decode painting", total=len(layers))
            for k, v in sorted(layers.items()):
                if k == "face":
                    painting += [nested_layers.Group(name="paintingface", layers=face, closed=False)]
                else:
                    tex = v.decode().transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                    tex = ImageOps.contain(tex, v.sizeDelta.round().tuple())
                    painting += [ps_layer(f"{v.name} [{v.texture2D.name}]", v.posBiased, v.meta.size, tex, True)]
                progress.update(task, advance=1)

        return nested_layers.nested_layers_to_psd(painting[::-1], color_mode=ColorMode.rgb)
