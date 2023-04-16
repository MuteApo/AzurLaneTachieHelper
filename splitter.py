import argparse
import os

from PIL import Image

from src.module import TextureHelper
from src.utility import get_rect_transform, read_img, save_img


class SplitHelper(TextureHelper):
    def split(self):
        _, _, x, y, w, h = get_rect_transform(
            os.path.join(self.dir, self._asset_name(self.chara))
        )

        pf_dir = os.path.join(self.dir, "paintingface")

        img_dict = {}
        for path, _, files in os.walk(os.path.join(pf_dir, "diff")):
            for img in [_ for _ in files if _.endswith(".png")]:
                print(os.path.join(path, img))
                full = read_img(os.path.join(pf_dir, img))
                diff = full.crop((x, y, x + w, y + h))
                save_img(diff, os.path.join(path, img))
                img_dict[img.split(".")[0]] = diff

        self._replace("paintingface", self._asset_name(self.chara), img_dict)


parser = argparse.ArgumentParser(description="Azur Lane Tachie Splitter")
parser.add_argument("chara", type=str, help="tachie to encode, eg. hailunna_h_rw")

if __name__ == "__main__":
    args = parser.parse_args().__dict__

    splitter = SplitHelper(**args)
    splitter.split()
