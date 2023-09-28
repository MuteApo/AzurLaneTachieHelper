import os
from math import ceil, floor

import numpy as np
from PIL import Image
from pytoshop.enums import ColorMode
from pytoshop.user import nested_layers
from tqdm import tqdm

from .TextureHelper import TextureHelper


class DecodeHelper(TextureHelper):
    def exec(self, dir: str, dump: bool) -> str:
        print("[INFO] Decoding paintingface")
        face = []
        for k, v in tqdm(sorted(self.faces.items(), key=lambda x: int(x[0]))):
            x, y = self.face_layer.posMin + self.bias
            sub = v.transform(v.size, Image.AFFINE, (1, 0, floor(x) - x, 0, 1, y - ceil(y)), Image.Resampling.BICUBIC)
            face += [self.ps_layer(sub, str(k), floor(x), ceil(y), False)]

        print("[INFO] Decoding painting")
        painting = []
        for k, v in tqdm(self.layers.items()):
            if k == "face":
                painting += [nested_layers.Group(name="paintingface", layers=face, closed=False)]
            else:
                sub = v.tex.transform(v.spriteSize.round().tuple(), Image.MESH, v.mesh, Image.Resampling.BICUBIC)
                sub = sub.transpose(Image.FLIP_TOP_BOTTOM)
                if dump:
                    sub.save(f"{os.path.join(dir, k)}.png")
                sub = sub.resize(v.canvasSize.round().tuple(), Image.Resampling.BICUBIC)
                x, y = v.posMin + self.bias
                sub = sub.transform(sub.size, Image.AFFINE, (1, 0, floor(x) - x, 0, 1, y - ceil(y)))
                painting += [self.ps_layer(sub, k, floor(x), ceil(y), True)]

        psd = nested_layers.nested_layers_to_psd(painting[::-1], color_mode=ColorMode.rgb)
        path = os.path.join(dir, self.name + ".psd")
        with open(path, "wb") as f:
            psd.write(f)

        return path

    def ps_layer(self, img: Image.Image, name: str, x: int, y: int, visible: bool) -> nested_layers.Layer:
        w, h = img.size
        r, g, b, a = img.split()
        channels = {i - 1: np.array(x) for i, x in enumerate([a, r, g, b])}
        layer = nested_layers.Image(
            name=name,
            visible=visible,
            top=self.size[1] - y - h,
            left=x,
            bottom=self.size[1] - y,
            right=x + w,
            channels=channels,
        )
        return layer
