import os
import re
import threading

import numpy as np
import UnityPy
from PIL import Image
from UnityPy import Environment
from UnityPy.classes import AssetBundle, GameObject, RectTransform, Texture2D
from UnityPy.enums import ClassIDType

from .Layer import Layer
from .utility import filter_env, read_img


def rt_get_name(rt: RectTransform) -> str:
    return rt.m_GameObject.read().m_Name.lower()


def rt_filter_child(rt: RectTransform, name: str) -> list[RectTransform]:
    rts: list[RectTransform] = [_.read() for _ in rt.m_Children]
    return [_ for _ in rts if rt_get_name(_) == name]


class AssetManager:
    def __init__(self):
        self.init()

    def init(self):
        self.meta: str = None
        self.name: str = None
        self.size: tuple[int, int] = None
        self.bias: tuple[float, float] = None
        self.deps: dict[str, str] = {}
        self.maps: dict[str, str] = {}
        self.layers: dict[str, Layer] = {}
        self.faces: dict[int, Image.Image] = {}
        self.repls: dict[str | int, Image.Image] = {}

    def analyze(self, file: str):
        self.init()

        self.meta = file

        env: Environment = UnityPy.load(file)
        abs: list[AssetBundle] = filter_env(env, AssetBundle)
        for dep in abs[0].m_Dependencies:
            path = os.path.join(os.path.dirname(file) + "/", dep)
            assert os.path.exists(path), f"Dependency not found: {dep}"
            self.deps[dep] = path
            env.load_file(path)

            for x in env.files[path].container.values():
                if x.type == ClassIDType.Sprite:
                    self.maps[dep] = x.read().name

        face = "paintingface/" + os.path.basename(file).strip("_n")
        path = os.path.join(os.path.dirname(file) + "/", face)
        if os.path.exists(path):
            self.deps[face] = path
            env.load_file(path)
            self.faces |= {
                eval(_.name): _.image
                for _ in filter_env(env, Texture2D)
                if re.match(r"^0|([1-9][0-9]*)$", _.name)
            }
        else:
            self.deps[face] = None

        print("[INFO] Dependencies:")
        [print("      ", _) for _ in self.deps.keys()]

        base_go: GameObject = list(env.container.values())[0].read()
        base_rt: RectTransform = base_go.m_Transform.read()
        base_layer = Layer(base_rt)

        self.name = base_layer.name

        self.layers = base_layer.flatten() | {"face": base_layer.get_child("face")}

        x_min, y_min = np.min([_.posMin for _ in self.layers.values()], 0)
        x_max, y_max = np.max([_.posMax for _ in self.layers.values()], 0)
        self.size = (round(x_max - x_min + 1), round(y_max - y_min + 1))
        self.bias = (-x_min, -y_min)

        [print(_) for _ in self.layers.values()]

    def load_paintings(self, workload: dict[str, str]):
        def load(name: str, path: str):
            print("      ", path)
            x, y = np.add(self.layers[name].posMin, self.bias)
            w, h = self.layers[name].sizeDelta
            sub = read_img(path).crop((x, y, x + w, y + h))
            self.repls[name] = sub.resize(self.layers[name].rawSpriteSize)

        tasks = [threading.Thread(target=load, args=(k, v)) for k, v in workload.items()]
        [_.start() for _ in tasks]
        [_.join() for _ in tasks]

    def load_faces(self, workload: dict[int, str]):
        def load(name: int, path: str):
            print("      ", path)
            self.repls[name] = read_img(path)

        tasks = [threading.Thread(target=load, args=(k, v)) for k, v in workload.items()]
        [_.start() for _ in tasks]
        [_.join() for _ in tasks]
