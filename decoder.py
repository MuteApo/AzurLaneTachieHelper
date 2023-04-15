import argparse
from pprint import pprint
from typing import List

import numpy as np
import UnityPy
from PIL import Image
from pytoshop.enums import ColorMode
from UnityPy.classes import AssetBundle, GameObject, MonoBehaviour, RectTransform

from src.module import TextureHelper
from src.utility import *


class DecodeHelper(TextureHelper):
    def _decode(self, name, rss):
        mesh_data = parse_obj(self._mesh_obj(name))
        enc_img = read_img(self._enc_tex(name))
        dec_img = decode_tex(enc_img, rss, *mesh_data.values())

        return dec_img

    def decode(self):
        env = UnityPy.load(self.chara)

        # resolve assetbundle dependencies
        abs: List[AssetBundle] = [
            _.read() for _ in env.objects if _.type.name == "AssetBundle"
        ]
        [self._extract(_) for _ in abs[0].m_Dependencies]

        mbs: List[MonoBehaviour] = [
            _.read() for _ in env.objects if _.type.name == "MonoBehaviour"
        ]
        base_go: GameObject = [_.read() for _ in env.container.values()][0]
        base_rt: RectTransform = base_go.m_Transform.read()
        base_children: List[RectTransform] = [_.read() for _ in base_rt.m_Children]
        base_rss, base_name, base_info = self._parse_rect(base_rt, mbs)
        base_pivot = base_info["m_SizeDelta"] * base_info["m_Pivot"]
        shape = base_info["m_SizeDelta"].astype(np.int32)

        print("[INFO] RectTransform:", base_rt, base_name)
        pprint(base_info)

        dec_img = self._decode(base_name, base_rss)

        full = Image.fromarray(dec_img).resize(tuple(shape), Image.Resampling.LANCZOS)
        save_img(np.array(full), self._dec_tex(base_name))

        ps_layer = [gen_ps_layer(full, base_name)]

        layers_rts: List[RectTransform] = [
            _ for _ in base_children if get_rt_name(_) == "layers"
        ]
        if len(layers_rts) > 0:
            layers_rt = layers_rts[0]
            layers_children: List[RectTransform] = [
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

                dec_img = self._decode(child_name, child_rss)

                child_pivot -= child_info["m_Pivot"] * child_info["m_SizeDelta"]
                x, y, w, h = clip_box(child_pivot, child_info["m_SizeDelta"], shape)

                sub = np.empty((*shape[::-1], 4), dtype=np.uint8)
                sub[y : y + h, x : x + w, :] = resize_img(dec_img, (w, h))[:, :, :]
                save_img(sub, self._dec_tex(child_name))

                ps_layer += [gen_ps_layer(Image.fromarray(sub), child_name)]

        group = [
            nested_layers.Group(
                name="painting",
                visible=True,
                opacity=255,
                layers=ps_layer[::-1],
                closed=False,
            )
        ]
        psd = nested_layers.nested_layers_to_psd(group, color_mode=ColorMode.rgb)
        with open(self.chara + ".psd", "wb") as fd:
            psd.write(fd)


parser = argparse.ArgumentParser(description="Azur Lane Tachie Decoder")
parser.add_argument("chara", type=str, help="tachie to decode, eg. hailunna_h_rw")

if __name__ == "__main__":
    args = parser.parse_args().__dict__

    decoder = DecodeHelper(**args)
    decoder.decode()
