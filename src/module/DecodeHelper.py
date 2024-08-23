from math import floor

import numpy as np
from PIL import Image
from pytoshop import PsdFile
from pytoshop.enums import ColorMode
from pytoshop.user import nested_layers
from rich.progress import Progress

from ..base import FaceLayer, Layer


def ps_layer(name: str, layer: Layer, img: Image.Image, visible: bool) -> nested_layers.Layer:
    """
    Generate a single psd layer.

    Parameters
    ----------
    name: str
        Name of the layer.
    layer: Layer
        Metainfo of the layer.
    img: Image.Image
        A Pillow Image to put on.
    visible: bool
        Whether initialized as visible.

    Returns
    -------
    psd_layer: nested_layers.Image
        A psd layer satisfying settings given above.
    """

    w, h = img.size
    x, y = layer.posBiased
    r, g, b, a = img.split()
    channels = {i - 1: np.array(x) for i, x in enumerate([a, r, g, b])}
    return nested_layers.Image(
        name=name,
        visible=visible,
        top=floor(layer.meta.size.Y - y - h),
        left=floor(x),
        bottom=floor(layer.meta.size.Y - y),
        right=floor(x + w),
        channels=channels,
    )


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

        Returns
        -------
        psd: PsdFile
            The resulting photoshop document.
        """

        painting = []
        with Progress() as progress:
            task = progress.add_task("Decode painting", total=len(layers))
            for k, v in sorted(layers.items()):
                if k == "face":
                    face = []
                    subtask = progress.add_task("Decode paintingface", total=len(faces))
                    for kk, vv in sorted(faces.items()):
                        tex = vv.decode(transpose=True)
                        face += [ps_layer(f"face #{kk}", v, tex, visible=False)]
                        progress.update(subtask, advance=1)
                    painting += [nested_layers.Group(name="paintingface", layers=face, closed=False)]
                else:
                    tex = v.decode(transpose=True, resize=True)
                    painting += [ps_layer(f"{v.name} [{v.texture2D.name}]", v, tex, visible=True)]
                progress.update(task, advance=1)

        return nested_layers.nested_layers_to_psd(painting, color_mode=ColorMode.rgb)
