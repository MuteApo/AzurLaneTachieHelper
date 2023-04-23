import argparse
import os
import UnityPy
from PIL import Image
from pytoshop.enums import ColorMode
from pytoshop.user import nested_layers
from UnityPy.classes import AssetBundle

from .PaintingHelper import PaintingHelper
from .utility import clip_box, decode_tex, gen_ps_layer, resize_img, filter_typename


class DecodeHelper(PaintingHelper):
    def get_dep(self, path: str) -> list[str]:
        self.env = UnityPy.load(path)
        self.abs: list[AssetBundle] = filter_typename(self.env, "AssetBundle")
        self.dep: list[str] = self.abs[0].m_Dependencies
        return self.dep

    def extract_dep(self, file: str, path: str):
        name = os.path.basename(file).split("_tex")[0].lower()
        self._extract(name, path)

    def _decode(self, name, rss):
        self.dec_img[name] = decode_tex(self.enc_img[name], rss, **self.mesh_obj[name])
        return self.dec_img[name]

    def act_base(self, base_name, base_rss, base_wh):
        dec_img = self._decode(base_name, base_rss)
        full = resize_img(dec_img, self.shape)
        self.ps_layer = [gen_ps_layer(full, base_name)]

    def act_child(self, child_name, child_rss, child_wh, child_pivot, child_sd):
        dec_img = self._decode(child_name, child_rss)
        sub = Image.new("RGBA", self.shape)
        x, y, w, h = clip_box(child_pivot, child_sd, self.shape)
        sub.paste(resize_img(dec_img, (w, h)), (x, y))
        self.ps_layer += [gen_ps_layer(sub, child_name)]

    def act_after(self):
        group = [
            nested_layers.Group(name="painting", layers=self.ps_layer[::-1], closed=False)
        ]
        psd = nested_layers.nested_layers_to_psd(group, color_mode=ColorMode.rgb)
        path = os.path.join(self.dir, self.file + ".psd")
        with open(path, "wb") as fd:
            psd.write(fd)
        return path


parser = argparse.ArgumentParser(description="Azur Lane Tachie Decoder")
parser.add_argument("chara", type=str, help="tachie to decode, eg. hailunna_h_rw")

if __name__ == "__main__":
    args = parser.parse_args().__dict__

    decoder = DecodeHelper(**args)
    decoder.exec()
