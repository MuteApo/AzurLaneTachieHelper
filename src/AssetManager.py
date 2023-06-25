import os
import re

import numpy as np
import UnityPy
from PIL import Image
from UnityPy import Environment
from UnityPy.classes import AssetBundle, GameObject, Mesh, RectTransform, Texture2D

from .Layer import Layer
from .utility import filter_env, read_img


class AssetManager:
    def __init__(self):
        self.init()

    def init(self):
        self.name = None
        self.size = None
        self.deps = {}
        self.layers: dict[str, Layer] = {}
        self.faces: dict[str, Image.Image] = {}
        self.repls: dict[str, Image.Image] = {}

    def _filter_child(self, rt: RectTransform, name: str):
        rts: list[RectTransform] = [_.read() for _ in rt.m_Children]
        return [_ for _ in rts if self._get_name(_) == name]

    def _get_name(self, rt: RectTransform):
        return rt.m_GameObject.read().m_Name.lower()

    def _parse_mesh(self, mesh: list[Mesh], tex2d: list[Texture2D]):
        if mesh == []:
            return self._quad_mesh(*tex2d[0].image.size)
        return {
            "v": np.array(mesh[0].m_Vertices).reshape((-1, 3))[:, :2],
            "vt": np.array(mesh[0].m_UV0).reshape((-1, 2)),
            "f": np.array(mesh[0].m_Indices).reshape((-1, 6))[:, (0, 1, 3, 4)],
        }

    def _quad_mesh(self, w: float, h: float):
        return {
            "v": np.array([[0, 0], [0, h], [w, h], [w, 0]]),
            "vt": np.array([[0, 0], [0, 1], [1, 1], [1, 0]]),
            "f": np.array([[0, 1, 2, 3]]),
        }

    def analyze(self, file: str):
        self.init()

        env: Environment = UnityPy.load(file)
        abs: list[AssetBundle] = filter_env(env, AssetBundle)
        for dep in abs[0].m_Dependencies:
            path = os.path.join(os.path.dirname(file) + "/", dep)
            assert os.path.exists(path), f"Dependency not found: {dep}"
            self.deps[dep] = path
            env.load_file(path)

        base_go: GameObject = [_.read() for _ in env.container.values()][0]
        base_rt: RectTransform = base_go.m_Transform.read()
        base_layer = Layer(base_rt)
        self.layers |= {base_layer.name: base_layer}

        self.name = base_layer.name
        self.size = base_layer.sizeDelta

        for layers_rt in self._filter_child(base_rt, "layers"):
            layers_layer = Layer(layers_rt, base_layer)
            for child_rt in [_.read() for _ in layers_rt.m_Children]:
                child_layer = Layer(child_rt, layers_layer)
                self.layers |= {child_layer.name: child_layer}

        face = "paintingface/" + os.path.basename(file).strip("_n")
        path = os.path.join(os.path.dirname(file) + "/", face)
        if os.path.exists(path):
            self.deps[face] = path
            env = UnityPy.load(path)
            for face_rt in self._filter_child(base_rt, "face"):
                self.layers |= {"face": Layer(face_rt, base_layer)}
                self.faces |= {
                    _.name: _.image.transpose(Image.FLIP_TOP_BOTTOM)
                    for _ in filter_env(env, Texture2D)
                    if re.match(r"[1-9][0-9]*", _.name)
                }
        else:
            self.deps[face] = None

        [print(_) for _ in self.layers.values()]

    def load_painting(self, name: str, path: str):
        x, y = self.layers[name].offset
        w, h = self.layers[name].sizeDelta
        sub = Image.new("RGBA", (w, h))
        sub.paste(read_img(path).crop((x, y, min(x + w, self.size[0]), min(y + h, self.size[1]))))
        self.repls |= {name: sub.resize(self.layers[name].rawSpriteSize, Image.Resampling.LANCZOS)}

    def load_face(self, dir: str):
        x, y = self.layers["face"].offset
        w, h = self.layers["face"].sizeDelta
        for path, _, files in os.walk(dir):
            for img in [_ for _ in files if _.endswith(".png")]:
                name = img.split(".png")[0]
                if name in self.faces:
                    print("      ", os.path.join(path + "/", img))
                    full = read_img(os.path.join(path, img))
                    self.repls |= {name: full.crop((x, y, x + w, y + h))}
