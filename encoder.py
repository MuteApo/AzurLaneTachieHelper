import argparse
from pprint import pprint

import numpy as np
import UnityPy
from PIL import Image
from UnityPy.classes import AssetBundle, GameObject, MonoBehaviour, RectTransform

from src.module import TextureHelper
from src.utility import (
    clip_box,
    convert,
    encode_tex,
    get_rt_name,
    parse_obj,
    read_img,
    resize_img,
    save_img,
)


class EncodeHelper(TextureHelper):
    def _encode(
        self,
        name: str,
        rss: tuple[int, int],
        enc_size: tuple[int, int],
        box: tuple[int, int, int, int] = None,
    ) -> Image.Image:
        mesh_data = parse_obj(self._mesh_obj(name))
        dec_img = read_img(self._dec_tex(name))
        dec_img = dec_img if box is None else dec_img.crop(box)
        enc_img = encode_tex(resize_img(dec_img, rss), enc_size, **mesh_data)

        return enc_img

    def encode(self):
        env = UnityPy.load(self.chara)

        # resolve assetbundle dependencies
        abs: list[AssetBundle] = [
            _.read() for _ in env.objects if _.type.name == "AssetBundle"
        ]
        enc_whs = {
            self._asset_name(_): self._extract(_, mesh_only=True)
            for _ in abs[0].m_Dependencies
        }

        mbs: list[MonoBehaviour] = [
            _.read() for _ in env.objects if _.type.name == "MonoBehaviour"
        ]
        base_go: GameObject = [_.read() for _ in env.container.values()][0]
        base_rt: RectTransform = base_go.m_Transform.read()
        base_children: list[RectTransform] = [_.read() for _ in base_rt.m_Children]
        base_rss, base_name, base_info = self._parse_rect(base_rt, mbs)
        base_pivot = base_info["m_SizeDelta"] * base_info["m_Pivot"]
        shape = base_info["m_SizeDelta"].astype(np.int32)

        print("[INFO]", base_rt, base_name)
        pprint(base_info)

        enc_img = self._encode(base_name, base_rss, enc_whs[base_name])
        save_img(enc_img, self._enc_tex(base_name))
        self._replace("painting", base_name + "_tex", {base_name: enc_img})

        layers_rts: list[RectTransform] = [
            _ for _ in base_children if get_rt_name(_) == "layers"
        ]
        if len(layers_rts) > 0:
            layers_rt = layers_rts[0]
            layers_children: list[RectTransform] = [
                _.read() for _ in layers_rt.m_Children
            ]
            layers_info = convert(layers_rt)
            layers_pivot = base_pivot + layers_info["m_LocalPosition"]

            print("[INFO]", layers_rt, get_rt_name(layers_rt))
            pprint(layers_info)

            for child_rt in layers_children:
                child_rss, child_name, child_info = self._parse_rect(child_rt, mbs)
                child_pivot = layers_pivot + child_info["m_LocalPosition"]

                print("[INFO]", child_rt, child_name)
                pprint(child_info)

                child_pivot -= child_info["m_Pivot"] * child_info["m_SizeDelta"]
                x, y, w, h = clip_box(child_pivot, child_info["m_SizeDelta"], shape)

                enc_img = self._encode(
                    child_name,
                    child_rss,
                    enc_whs[child_name],
                    (x, y, x + w, y + h),
                )
                save_img(enc_img, self._enc_tex(child_name))
                self._replace(
                    "painting",
                    child_name + "_tex",
                    {child_name: enc_img},
                )


parser = argparse.ArgumentParser(description="Azur Lane Tachie Encoder")
parser.add_argument("chara", type=str, help="tachie to encode, eg. hailunna_h_rw")

if __name__ == "__main__":
    args = parser.parse_args().__dict__

    encoder = EncodeHelper(**args)
    encoder.encode()
