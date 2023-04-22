import os
from pprint import pprint

import numpy as np
import UnityPy
from UnityPy.classes import AssetBundle, GameObject, MonoBehaviour, RectTransform

from .utility import convert, filter_typename, get_rt_name
from .TextureHelper import TextureHelper


class PaintingHelper(TextureHelper):
    def get_dependency(self) -> list[str]:
        self.env = UnityPy.load(self.path)
        self.abs: list[AssetBundle] = filter_typename(self.env, "AssetBundle")
        return self.abs[0].m_Dependencies

    def extract_dependency(self, dependency_list, output_dir):
        self.whs = {
            self._asset_name(os.path.basename(_)).lower(): self._extract(
                _, output_dir, mesh_only=False
            )
            for _ in dependency_list
        }

    def act_base(self, base_name, base_rss, base_wh):
        raise NotImplementedError

    def act_child(self, child_name, child_rss, child_wh, child_pivot, child_sd):
        raise NotImplementedError

    def act_after(self):
        raise NotImplementedError

    def exec(self, dir):
        mbs: list[MonoBehaviour] = filter_typename(self.env, "MonoBehaviour")
        base_go: GameObject = [_.read() for _ in self.env.container.values()][0]
        base_rt: RectTransform = base_go.m_Transform.read()
        base_children: list[RectTransform] = [_.read() for _ in base_rt.m_Children]
        base_rss, base_name, base_info = self._parse_rect(base_rt, mbs)
        base_pivot = base_info["m_SizeDelta"] * base_info["m_Pivot"]
        self.shape = tuple(base_info["m_SizeDelta"].astype(np.int32))

        print("[INFO] RectTransform:", base_rt, base_name)
        pprint(base_info)

        self.act_base(os.path.join(dir, base_name), base_rss, self.whs[base_name.lower()])

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
                child_pivot -= child_info["m_Pivot"] * child_info["m_SizeDelta"]

                print("[INFO]", child_rt, child_name)
                pprint(child_info)

                self.act_child(
                    os.path.join(dir, child_name),
                    child_rss,
                    self.whs[child_name.lower()],
                    child_pivot,
                    child_info["m_SizeDelta"],
                )

        self.act_after(dir)
