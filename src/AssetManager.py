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

from .utility import filter_env, raw_name


class AssetManager:
    def __init__(self):
        self.init()

    def init(self):
        self.metas = {}
        self.deps = []
        self.name = None
        self.size = None

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

    def analyze(self, file: str):
        self.init()

        env: Environment = UnityPy.load(file)
        abs: list[AssetBundle] = filter_env(env, AssetBundle)

        self.deps: list[str] = abs[0].m_Dependencies

        base_go: GameObject = [_.read() for _ in env.container.values()][0]
        base_rt: RectTransform = base_go.m_Transform.read()
        base_name = self._get_name(base_rt)
        base_info = self._parse_rt(base_rt) | self._get_rss(base_rt)
        base_info |= {"Offset": (0, 0)}

        self.name = base_name
        self.size = base_info["SizeDelta"]

        self.metas[base_name] = base_info

        for layers_rt in self._filter_child(base_rt, "layers"):
            layers_info = self._parse_rt(layers_rt)

            for child_rt in [_.read() for _ in layers_rt.m_Children]:
                child_name = self._get_name(child_rt)
                child_info = self._parse_rt(child_rt) | self._get_rss(child_rt)
                child_info["Offset"] = tuple(
                    np.round(
                        base_info["Pivot"] * base_info["SizeDelta"]
                        + layers_info["LocalPosition"]
                        + child_info["LocalPosition"]
                        - child_info["Pivot"] * child_info["SizeDelta"]
                    ).astype(np.int32)
                )

                self.metas[child_name] = child_info

        for face_rt in self._filter_child(base_rt, "face"):
            face_info = self._parse_rt(face_rt)
            face_info["Offset"] = tuple(
                np.round(
                    base_info["Pivot"] * base_info["SizeDelta"]
                    + face_info["LocalPosition"]
                    - face_info["Pivot"] * face_info["SizeDelta"]
                ).astype(np.int32)
            )

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
            self.metas["face"] |= {"diff": tex2d}
        else:
            self.metas[raw_name(dep).lower()] |= {
                "mesh": self._parse_mesh(mesh[0]),
                "enc": tex2d[0].image.transpose(Image.FLIP_TOP_BOTTOM),
                "whs": tex2d[0].image.size,
            }
