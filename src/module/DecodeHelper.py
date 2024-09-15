from math import floor

import numpy as np
from PIL import Image
from pytoshop import PsdFile
from pytoshop.enums import ColorMode
from pytoshop.user import nested_layers
from rich.progress import Progress

from ..base import FaceLayer, Layer


class DecodeHelper:
    @staticmethod
    def ps_layer(name: str, layer: Layer, img: Image.Image, visible: bool) -> nested_layers.Image:
        """
        Generate a single psd layer.

        Parameters
        ----------
        name: str
            The name of the layer.
        layer: Layer
            The `Metainfo` of the layer.
        img: Image.Image
            The Pillow Image to put on.
        visible: bool
            Whether initialized as visible.

        Returns
        -------
        psd_layer: nested_layers.Image
            The psd layer satisfying settings given above.
        """

        w, h = img.size
        x, y = layer.posBiased
        r, g, b, a = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM).split()
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

    @staticmethod
    def exec(layers: dict[str, Layer], faces: dict[str, FaceLayer]) -> PsdFile:
        """
        Decode layers of a painting along with paintingface and return file path of the dumped psd.

        Parameters
        ----------
        layers: dict[str, Layer]
            The dict containing each of the painting layers.
        faces: dict[str, FaceLayer]
            The dict containing each of the paintingface images, as pseudo-layers.

        Returns
        -------
        psd: PsdFile
            The resulting photoshop document.
        """

        painting = []
        with Progress() as progress:
            task = progress.add_task("Decode painting", total=len(layers))
            for k, v in layers.items():
                if k == "face":
                    face = []
                    subtask = progress.add_task("Decode paintingface", total=len(faces))
                    for kk, vv in sorted(faces.items()):
                        face += [DecodeHelper.ps_layer(f"face #{kk}", v, vv.decode(), visible=False)]
                        progress.update(subtask, advance=1)
                    painting += [nested_layers.Group(name="paintingface", layers=face, closed=False)]
                else:
                    painting += [DecodeHelper.ps_layer(f"{v.name} [{v.texture2D.name}]", v, v.decode(), visible=True)]
                progress.update(task, advance=1)

        return nested_layers.nested_layers_to_psd(painting[::-1], color_mode=ColorMode.rgb)
