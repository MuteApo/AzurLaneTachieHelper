from math import floor

import numpy as np
from PIL import Image
from pytoshop import PsdFile
from pytoshop.enums import ColorMode
from pytoshop.user import nested_layers
from rich.progress import Progress

from ..base.Layer import FaceLayer, Layer


def ps_layer(name: str, layer: Layer, img: Image.Image, visible: bool) -> nested_layers.Image:

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


class DecodeHelper:
    @staticmethod
    def exec(layers: dict[str, Layer], faces: dict[str, FaceLayer]) -> PsdFile:
        painting = []
        with Progress() as progress:
            task = progress.add_task("Decode painting", total=len(layers))
            for k, v in layers.items():
                if k == "face":
                    face = []
                    subtask = progress.add_task("Decode paintingface", total=len(faces))
                    for kk, vv in sorted(faces.items()):
                        face += [ps_layer(f"face #{kk}", v, vv.decode, visible=False)]
                        progress.update(subtask, advance=1)
                    painting += [nested_layers.Group(name="paintingface", layers=face, closed=False)]
                else:
                    painting += [ps_layer(f"{v.name} [{v.texture2D.m_Name}]", v, v.decode, visible=True)]
                progress.update(task, advance=1)

        return nested_layers.nested_layers_to_psd(painting[::-1], color_mode=ColorMode.rgb)
