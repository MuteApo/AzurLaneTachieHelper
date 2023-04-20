import argparse

from PIL import Image
from pytoshop.enums import ColorMode
from pytoshop.user import nested_layers

from .module import PaintingHelper
from .utility import (
    clip_box,
    decode_tex,
    gen_ps_layer,
    parse_obj,
    read_img,
    resize_img,
    save_img,
)


class DecodeHelper(PaintingHelper):
    def _decode(self, name, rss):
        mesh_data = parse_obj(self._mesh_obj(name))
        enc_img = read_img(self._enc_tex(name))
        dec_img = decode_tex(enc_img, rss, **mesh_data)

        return dec_img

    def act_base(self, base_name, base_rss, base_wh):
        dec_img = self._decode(base_name, base_rss)
        save_img(dec_img, self._dec_tex(base_name))

        full = resize_img(dec_img, self.shape)
        self.ps_layer = [gen_ps_layer(full, base_name)]

    def act_child(self, child_name, child_rss, child_wh, child_pivot, child_sd):
        x, y, w, h = clip_box(child_pivot, child_sd, self.shape)

        dec_img = self._decode(child_name, child_rss)
        save_img(dec_img, self._dec_tex(child_name))

        sub = Image.new("RGBA", self.shape)
        sub.paste(resize_img(dec_img, (w, h)), (x, y))
        self.ps_layer += [gen_ps_layer(sub, child_name)]

    def act_after(self):
        group = [
            nested_layers.Group(name="painting", layers=self.ps_layer[::-1], closed=False)
        ]
        psd = nested_layers.nested_layers_to_psd(group, color_mode=ColorMode.rgb)
        with open(self.chara + ".psd", "wb") as fd:
            psd.write(fd)


parser = argparse.ArgumentParser(description="Azur Lane Tachie Decoder")
parser.add_argument("chara", type=str, help="tachie to decode, eg. hailunna_h_rw")

if __name__ == "__main__":
    args = parser.parse_args().__dict__

    decoder = DecodeHelper(**args)
    decoder.exec(mesh_only=False)
