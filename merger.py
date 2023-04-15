import argparse
import os
from typing import List

import numpy as np
import pytoshop
import UnityPy
import win32api
import win32con
from PIL import Image
from pytoshop.enums import ColorMode
from UnityPy.classes import Texture2D

from src.module import TextureHelper
from src.utility import *


class MergeHelper(TextureHelper):
    def merge(self):
        base, _, x, y, w, h = get_rect_transform(
            os.path.join(self.dir, self._asset_name(self.chara))
        )

        pf_dir = os.path.join(self.dir, "paintingface")
        check_dir(pf_dir, "diff")

        asset_path = os.path.join(pf_dir, self._asset_name(self.chara))
        assert os.path.exists(asset_path), f"file {asset_path} not found"
        env = UnityPy.load(asset_path)

        print("[INFO] Asset bundle:", asset_path)

        tex2d: List[Texture2D] = [
            _.read() for _ in env.objects if _.type.name == "Texture2D"
        ]
        [_.image.save(os.path.join(pf_dir, "diff", _.m_Name + ".png")) for _ in tex2d]

        ps_layer = []

        for path, _, files in os.walk(os.path.join(pf_dir, "diff")):
            for img in [_ for _ in files if _.endswith(".png")]:
                print(os.path.join(path, img))
                diff = read_img(os.path.join(path, img))
                main = np.empty(
                    (*base["m_SizeDelta"].astype(np.int32)[::-1], 4), dtype=np.uint8
                )
                main[y : y + h, x : x + w] = diff[:, :]
                save_img(main, os.path.join(pf_dir, img))
                ps_layer += [gen_ps_layer(Image.fromarray(main), img.split(".")[0])]

        group = [
            nested_layers.Group(
                name="paintingface",
                visible=False,
                opacity=255,
                layers=ps_layer[::-1],
                closed=False,
            )
        ]
        ps_dst = self.chara + ".psd"
        ps_src = self.chara + "~.psd"
        os.rename(ps_dst, ps_src)
        win32api.SetFileAttributes(ps_src, win32con.FILE_ATTRIBUTE_HIDDEN)
        with open(ps_src, "rb") as f:
            group += nested_layers.psd_to_nested_layers(pytoshop.read(f))
            psd = nested_layers.nested_layers_to_psd(group, color_mode=ColorMode.rgb)
            with open(ps_dst, "wb") as fd:
                psd.write(fd)
        os.remove(ps_src)


parser = argparse.ArgumentParser(description="Azur Lane Tachie Merger")
parser.add_argument("chara", type=str, help="tachie to encode, eg. hailunna_h_rw")

if __name__ == "__main__":
    args = parser.parse_args().__dict__

    merger = MergeHelper(**args)
    merger.merge()
