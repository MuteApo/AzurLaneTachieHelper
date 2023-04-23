import argparse

from .PaintingHelper import PaintingHelper
from .utility import clip_box, encode_tex, read_img, resize_img


class EncodeHelper(PaintingHelper):
    def from_decoder(self, decoder: PaintingHelper):
        self.env = decoder.env
        self.mesh_obj = decoder.mesh_obj
        self.whs = decoder.whs

    def load_replacer(self, name: str, path: str):
        self.dec_img[name] = read_img(path)

    def _encode(self, name, rss, size, box=None):
        self.dec_img[name] = resize_img(self.dec_img[name].crop(box), rss)
        self.enc_img[name] = encode_tex(self.dec_img[name], size, **self.mesh_obj[name])
        return self.enc_img[name]

    def act_base(self, base_name, base_rss, base_wh):
        enc_img = self._encode(base_name, base_rss, base_wh)
        self._replace("painting", base_name + "_tex", {base_name: enc_img})

    def act_child(self, child_name, child_rss, child_wh, child_pivot, child_sd):
        x, y, w, h = clip_box(child_pivot, child_sd, self.shape)
        enc_img = self._encode(child_name, child_rss, child_wh, (x, y, x + w, y + h))
        self._replace("painting", child_name + "_tex", {child_name: enc_img})

    def act_after(self):
        pass


parser = argparse.ArgumentParser(description="Azur Lane Tachie Encoder")
parser.add_argument("chara", type=str, help="tachie to encode, eg. hailunna_h_rw")

if __name__ == "__main__":
    args = parser.parse_args().__dict__

    encoder = EncodeHelper(**args)
    encoder.exec(mesh_only=True)
