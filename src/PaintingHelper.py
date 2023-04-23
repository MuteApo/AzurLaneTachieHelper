import numpy as np
from UnityPy.classes import GameObject, MonoBehaviour, RectTransform

from .TextureHelper import TextureHelper
from .utility import convert, filter_typename, get_rt_name


class PaintingHelper(TextureHelper):
    def act_base(self, base_name, base_rss, base_wh):
        raise NotImplementedError

    def act_child(self, child_name, child_rss, child_wh, child_pivot, child_sd):
        raise NotImplementedError

    def act_after(self):
        raise NotImplementedError

    def exec(self, dir):
        self.dir = dir
        mbs: list[MonoBehaviour] = filter_typename(self.env, "MonoBehaviour")
        base_go: GameObject = [_.read() for _ in self.env.container.values()][0]
        base_rt: RectTransform = base_go.m_Transform.read()
        base_children: list[RectTransform] = [_.read() for _ in base_rt.m_Children]
        base_rss, base_name, base_info = self._parse_rect(base_rt, mbs)
        base_pivot = base_info["m_SizeDelta"] * base_info["m_Pivot"]
        self.shape = tuple(base_info["m_SizeDelta"].astype(np.int32))

        print("[INFO] RectTransform:", base_rt, base_name)
        [print("      ", k + ":", v) for k, v in base_info.items()]

        self.act_base(base_name, base_rss, self.whs[base_name.lower()])

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

            print("[INFO] RectTransform:", layers_rt, get_rt_name(layers_rt))
            [print("      ", k + ":", v) for k, v in layers_info.items()]

            for child_rt in layers_children:
                child_rss, child_name, child_info = self._parse_rect(child_rt, mbs)
                child_pivot = layers_pivot + child_info["m_LocalPosition"]
                child_pivot -= child_info["m_Pivot"] * child_info["m_SizeDelta"]

                print("[INFO] RectTransform:", child_rt, child_name)
                [print("      ", k + ":", v) for k, v in child_info.items()]

                self.act_child(
                    child_name,
                    child_rss,
                    self.whs[child_name.lower()],
                    child_pivot,
                    child_info["m_SizeDelta"],
                )

        return self.act_after()
