import argparse

from .module import PaintingHelper
from .utility import clip_box, encode_tex, parse_obj, read_img, resize_img, save_img


class EncodeHelper(PaintingHelper):
    def _encode(self, name, rss, enc_size, box=None):
        mesh_data = parse_obj(self._mesh_obj(name))
        dec_img = read_img(self._dec_tex(name))
        dec_img = dec_img if box is None else dec_img.crop(box)
        enc_img = encode_tex(resize_img(dec_img, rss), enc_size, **mesh_data)

        return enc_img

    def act_base(self, base_name, base_rss, base_wh):
        enc_img = self._encode(base_name, base_rss, base_wh)
        save_img(enc_img, self._enc_tex(base_name))
        self._replace("painting", base_name + "_tex", {base_name: enc_img})

    def act_child(self, child_name, child_rss, child_wh, child_pivot, child_sd):
        x, y, w, h = clip_box(child_pivot, child_sd, self.shape)

        enc_img = self._encode(child_name, child_rss, child_wh, (x, y, x + w, y + h))
        save_img(enc_img, self._enc_tex(child_name))
        self._replace("painting", child_name + "_tex", {child_name: enc_img})

    def act_after(self):
        pass


parser = argparse.ArgumentParser(description="Azur Lane Tachie Encoder")
parser.add_argument("chara", type=str, help="tachie to encode, eg. hailunna_h_rw")

if __name__ == "__main__":
    args = parser.parse_args().__dict__

    encoder = EncodeHelper(**args)
    encoder.exec(mesh_only=True)
