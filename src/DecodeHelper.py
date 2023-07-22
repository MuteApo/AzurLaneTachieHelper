import os
from typing import Literal

import numpy as np
from PIL import Image
from pytoshop.enums import ColorMode
from pytoshop.user import nested_layers
from tqdm import tqdm

from .TextureHelper import TextureHelper


class DecodeHelper(TextureHelper):
    def exec(self, dir: str, dump: bool | Literal["true", "false"]) -> str:
        print(dump)
        print("[INFO] Decoding painting")
        painting = []
        for k, v in tqdm(self.layers.items()):
            if k != "face":
                sub = self.decode(v.mesh, v.tex, v.rawSpriteSize)
                if dump in [True, "true"]:
                    sub.transpose(Image.FLIP_TOP_BOTTOM).save(f"{os.path.join(dir, k)}.png")
                full = Image.new("RGBA", self.size)
                x, y = np.add(v.posMin, self.bias)
                full.paste(sub.resize(v.sizeDelta), (round(x), round(y)))
                painting += [self.ps_layer(full, k, True)]

        print("[INFO] Decoding paintingface")
        face = []
        for k, v in tqdm(sorted(self.faces.items())):
            full = Image.new("RGBA", self.size)
            x, y = np.add(self.face_layer.posMin, self.bias)
            full.paste(v, (round(x), round(y)))
            face += [self.ps_layer(full, str(k), False)]

        layers = [
            nested_layers.Group(name="paintingface", layers=face, closed=False),
            nested_layers.Group(name="painting", layers=painting[::-1], closed=False),
        ]
        psd = nested_layers.nested_layers_to_psd(layers, color_mode=ColorMode.rgb)
        path = os.path.join(dir, self.name + ".psd")
        with open(path, "wb") as f:
            psd.write(f)

        return path

    def decode(self, mesh: dict, enc: Image.Image, rss: tuple[int, int]) -> Image.Image:
        dec = Image.new("RGBA", rss)

        vs, ts, fs = mesh.values()
        for f in fs:
            l, b, r, t = self._measure(np.stack(vs[f], -1))
            box = self._measure(np.stack(ts[f], -1))
            dec.paste(enc.crop(box), (round(l), round(b)))

        return dec

    def _measure(self, data: np.ndarray) -> tuple[int, int, int, int]:
        l, b = data.min(-1)
        r, t = data.max(-1)

        w = round(r - l)
        if w > round(w / 4) * 4:
            l += 1
        if w < round(w / 4) * 4:
            r += 1

        h = round(t - b)
        if h > round(h / 4) * 4:
            b += 1
        if h < round(h / 4) * 4:
            t += 1

        return l, b, r, t

    def ps_layer(self, img: Image.Image, name: str, visible: bool) -> nested_layers.Layer:
        w, h = img.size
        r, g, b, a = img.transpose(Image.FLIP_TOP_BOTTOM).split()
        channels = {i - 1: np.array(x) for i, x in enumerate([a, r, g, b])}
        layer = nested_layers.Image(
            name=name, visible=visible, bottom=h, right=w, channels=channels
        )
        return layer
