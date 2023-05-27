import os
import re

import numpy as np
import UnityPy
from PIL import Image
from UnityPy import Environment
from UnityPy.classes import (
    AssetBundle,
    GameObject,
    Mesh,
    MonoBehaviour,
    RectTransform,
    Texture2D,
)

from .utility import filter_env, raw_name, read_img


class AssetManager:
    def __init__(self):
        self.init()

    def init(self):
        self.name = None
        self.size = None
        self.metas = {}
        self.deps = []

    def _filter_child(self, rt: RectTransform, name: str):
        rts: list[RectTransform] = [_.read() for _ in rt.m_Children]
        return [_ for _ in rts if self._get_name(_) == name]

    def _get_name(self, rt: RectTransform):
        return rt.m_GameObject.read().m_Name.lower()

    def _get_rss(self, rt: RectTransform):
        go: GameObject = rt.m_GameObject.read()
        mb: MonoBehaviour = go.m_Components[2].read()
        return {"RawSpriteSize": tuple(int(_) for _ in mb.mRawSpriteSize.values())}

    def _parse_rt(self, rt: RectTransform):
        items = {k: np.array([*v.values()]) for k, v in rt.to_dict().items() if isinstance(v, dict)}
        return {
            "LocalPosition": items["m_LocalPosition"][:2],
            "SizeDelta": tuple(items["m_SizeDelta"].astype(np.int32)),
            "Pivot": items["m_Pivot"],
        }

    def _parse_mesh(self, mesh: Mesh):
        return {
            "v": np.array(mesh.m_Vertices).reshape((-1, 3))[:, :2],
            "vt": np.array(mesh.m_UV0).reshape((-1, 2)),
            "f": np.array(mesh.m_Indices).reshape((-1, 6))[:, (0, 1, 3, 4)],
        }

    def _calc_layer_offset(self, base: dict, layers: dict, child: dict) -> tuple[int, int]:
        base_pivot = base["Pivot"] * base["SizeDelta"]
        layers_pivot = base_pivot + layers["LocalPosition"]
        child_pivot = layers_pivot + child["LocalPosition"]
        child_offset = child_pivot - child["Pivot"] * child["SizeDelta"]
        return tuple(np.round(child_offset).astype(np.int32))

    def _calc_face_offset(self, base: dict, face: dict) -> tuple[int, int]:
        base_pivot = base["Pivot"] * base["SizeDelta"]
        face_pivot = base_pivot + face["LocalPosition"]
        face_offset = face_pivot - face["Pivot"] * face["SizeDelta"]
        return tuple(np.round(face_offset).astype(np.int32))

    def analyze(self, file: str):
        self.init()

        env: Environment = UnityPy.load(file)
        abs: list[AssetBundle] = filter_env(env, AssetBundle)

        base_go: GameObject = [_.read() for _ in env.container.values()][0]
        base_rt: RectTransform = base_go.m_Transform.read()
        base_name = self._get_name(base_rt)
        base_info = self._parse_rt(base_rt) | self._get_rss(base_rt)
        base_info["Offset"] = (0, 0)

        self.name = base_name
        self.size = base_info["SizeDelta"]
        self.metas[base_name] = base_info

        for layers_rt in self._filter_child(base_rt, "layers"):
            layers_info = self._parse_rt(layers_rt)
            for child_rt in [_.read() for _ in layers_rt.m_Children]:
                child_name = self._get_name(child_rt)
                child_info = self._parse_rt(child_rt) | self._get_rss(child_rt)
                child_info["Offset"] = self._calc_layer_offset(base_info, layers_info, child_info)

                self.metas[child_name] = child_info

        self.deps: list[str] = [_ for _ in abs[0].m_Dependencies if raw_name(_) in self.metas]

        for face_rt in self._filter_child(base_rt, "face"):
            face_info = self._parse_rt(face_rt)
            face_info["Offset"] = self._calc_face_offset(base_info, face_info)

            self.metas["face"] = face_info

    def extract(self, dep: str, path: str, is_paintingface: bool = False):
        env: Environment = UnityPy.load(path)

        # extract texture2d
        tex2d: list[Texture2D] = filter_env(env, Texture2D)

        # extract mesh
        mesh: list[Mesh] = filter_env(env, Mesh)
        if len(mesh) == 0:
            env = UnityPy.load(path.split("_tex")[0] + "_n_tex")
            mesh: list[Mesh] = filter_env(env, Mesh)

        if is_paintingface:
            self.metas["face"] |= {
                "diff": {_.name: _.image.transpose(Image.FLIP_TOP_BOTTOM) for _ in tex2d}
            }
        else:
            self.metas[raw_name(dep).lower()] |= {
                "mesh": self._parse_mesh(mesh[0]),
                "enc": tex2d[0].image.transpose(Image.FLIP_TOP_BOTTOM),
                "whs": tex2d[0].image.size,
            }

    def load_painting(self, name: str, path: str):
        x, y = self.metas[name]["Offset"]
        w, h = self.metas[name]["SizeDelta"]
        sub = Image.new("RGBA", (w, h))
        sub.paste(read_img(path).crop((x, y, min(x + w, self.size[0]), min(y + h, self.size[1]))))
        self.metas[name] |= {
            "rep": sub.resize(self.metas[name]["RawSpriteSize"], Image.Resampling.LANCZOS)
        }

    def load_face(self, dir: str):
        x, y = self.metas["face"]["Offset"]
        w, h = self.metas["face"]["SizeDelta"]
        img_dict = {}
        for path, _, files in os.walk(dir):
            for img in [_ for _ in files if _.endswith(".png")]:
                name = img.split(".png")[0]
                if name in self.metas["face"]["diff"]:
                    print("      ", os.path.join(path + "/", img))
                    full = read_img(os.path.join(path, img))
                    img_dict[name] = full.crop((x, y, x + w, y + h))

        self.metas["face"] |= {"rep": img_dict}
