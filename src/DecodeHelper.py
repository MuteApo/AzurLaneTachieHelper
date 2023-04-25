import os

import numpy as np
from PIL import Image
from pytoshop.enums import ColorMode
from pytoshop.user import nested_layers

from .PaintingHelper import PaintingHelper
from .utility import gen_ps_layer, get_img_area, resize_img


class DecodeHelper(PaintingHelper):
    def exec(self, dir: str):
        layers = []
        for k, v in self.metas.items():
            v["dec"] = self.decode(
                self.metas[k]["mesh"],
                self.metas[k]["enc"],
                self.metas[k]["RawSpriteSize"],
            )
            sub = Image.new("RGBA", self.size)
            offset = tuple(np.round(self.metas[k]["Offset"]).astype(np.int32))
            sub.paste(resize_img(v["dec"], self.metas[k]["SizeDelta"]), offset)
            layers += [gen_ps_layer(sub, k)]

        group = [nested_layers.Group(name="painting", layers=layers, closed=False)]
        psd = nested_layers.nested_layers_to_psd(group, color_mode=ColorMode.rgb)
        path = os.path.join(dir, self.name + ".psd")
        with open(path, "wb") as f:
            psd.write(f)

        return path

    def decode(self, mesh: dict, enc: Image.Image, rss: tuple) -> Image.Image:
        v, vt, f = mesh.values()
        dec = Image.new("RGBA", rss)

        for i, x in enumerate(f):
            # print(f"---{i + 1}---")
            # print(x)

            lb1, ru1, wh1 = get_img_area(v[x])
            lb2, ru2, wh2 = get_img_area(vt[x] * enc.size)
            # print(lb1, ru1, wh1)
            # print(lb2, ru2, wh2)
            # ru2[0] -= wh2[0] - wh1[0]
            # lb2[1] += wh2[1] - wh1[1]

            dec.paste(enc.crop((*lb2, *ru2)), (*lb1,))

        return dec
