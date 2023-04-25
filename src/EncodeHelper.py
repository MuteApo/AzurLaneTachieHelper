import numpy as np

from .PaintingHelper import PaintingHelper
from .utility import read_img, resize_img


class EncodeHelper(PaintingHelper):
    def load_replacer(self, name: str, path: str):
        self.metas[name] |= {"rep": read_img(path)}

    def exec(self, dir: str):
        layers = []
        for k in self.metas.keys():
            x, y = np.round(self.metas[k]["Offset"]).astype(np.int32)
            w, h = self.metas[k]["SizeDelta"]
            sub = resize_img(
                self.metas[k]["rep"].crop((x, y, x + w, y + h)), self.metas[k]["RawSpriteSize"]
            )
            layers += [self._replace(dir, "painting/", k + "_tex", {k: sub})]

        return "\n".join(layers)
