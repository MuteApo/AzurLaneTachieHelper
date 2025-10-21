from concurrent.futures import ThreadPoolExecutor, as_completed
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
        with Progress() as progress, ThreadPoolExecutor(max_workers=len(layers) + len(faces)) as executor:
            painting_map = {}
            task = progress.add_task("Decode painting", total=len(layers))
            future_to_key = {}

            for k, v in layers.items():
                if k == "face":
                    subtask = progress.add_task("Decode paintingface", total=len(faces))

                    def process_faces_group(layer, face_items):
                        def process_one_face(item):
                            kk, vv = item
                            result = ps_layer(f"face #{kk}", layer, vv.decode, visible=False)
                            progress.update(subtask, advance=1)
                            return result

                        face_group_layers = list(executor.map(process_one_face, face_items))
                        return nested_layers.Group(name="paintingface", layers=face_group_layers, closed=False)

                    future = executor.submit(process_faces_group, v, sorted(faces.items()))
                    future_to_key[future] = k
                else:
                    future = executor.submit(ps_layer, f"{v.name} [{v.texture2D.m_Name}]", v, v.decode, True)
                    future_to_key[future] = k

            for future in as_completed(future_to_key):
                k = future_to_key[future]
                painting_map[k] = future.result()
                progress.update(task, advance=1)

            painting = [painting_map[k] for k in layers]

        return nested_layers.nested_layers_to_psd(painting[::-1], color_mode=ColorMode.rgb)
