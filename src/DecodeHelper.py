import os

import numpy as np
from PIL import Image
from pytoshop.enums import ColorMode
from pytoshop.user import nested_layers
from tqdm import tqdm

from .Layer import Layer
from .TextureHelper import TextureHelper


class DecodeHelper(TextureHelper):
    def exec(self, dir: str, dump: bool) -> str:
        print("[INFO] Decoding painting")
        painting = []
        filtered: dict[str, Layer] = {k: v for k, v in self.layers.items() if k != "face"}
        for k, v in tqdm(sorted(filtered.items(), key=lambda x: x[1].depth)):
            sub = self.decode(v)
            if dump:
                sub.save(f"{os.path.join(dir, k)}.png")
            sub = sub.resize(v.canvasSize.round())
            x, y = v.posMin + self.bias
            painting += [self.ps_layer(sub, k, x, y, True)]

        print("[INFO] Decoding paintingface")
        face = []
        for k, v in tqdm(sorted(self.faces.items())):
            x, y = self.face_layer.posMin + self.bias
            face += [self.ps_layer(v, str(k), x, y, False)]

        layers = [
            nested_layers.Group(name="paintingface", layers=face, closed=False),
            nested_layers.Group(name="painting", layers=painting[::-1], closed=False),
        ]
        psd = nested_layers.nested_layers_to_psd(layers, color_mode=ColorMode.rgb)
        path = os.path.join(dir, self.name + ".psd")
        with open(path, "wb") as f:
            psd.write(f)

        return path

    def decode(self, v: Layer) -> Image.Image:
        dec = Image.new("RGBA", v.spriteSize)
        vs, ts, fs = v.mesh.values()
        for f in fs:
            l, b, r, t = self._measure(vs[f])
            box = self._measure(ts[f])
            dec.paste(v.tex.crop(box), (round(l), round(b)))
        return dec.transpose(Image.FLIP_TOP_BOTTOM)

    def _measure(self, data: np.ndarray) -> tuple[float, float, float, float]:
        l, b = data.min(0)
        r, t = data.max(0)

        # w = round(r - l)
        # # if w > round(w / 4) * 4:
        # #     l += 1
        # if w < round(w / 4) * 4:
        #     r += 1

        # h = round(t - b)
        # if h > round(h / 4) * 4:
        #     b += 1
        # if h < round(h / 4) * 4:
        #     t += 1

        return l, b, r, t

    def ps_layer(
        self, img: Image.Image, name: str, x: float, y: float, visible: bool
    ) -> nested_layers.Layer:
        w, h = img.size
        r, g, b, a = img.split()
        channels = {i - 1: np.array(x) for i, x in enumerate([a, r, g, b])}
        layer = nested_layers.Image(
            name=name,
            visible=visible,
            top=round(self.size[1] - y - h),
            left=round(x),
            bottom=round(self.size[1] - y),
            right=round(x + w),
            channels=channels,
        )
        return layer
