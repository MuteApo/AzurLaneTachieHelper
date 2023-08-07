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
from .utility import filter_env, prod, read_img

metas = {
    "herohrzicon": {
        "sprite": (272, 80),
        "tex2d": (360, 80),
        "pivot": (0.25, 0.6),
        "scale": 0.5,
    },
    "shipyardicon": {
        "sprite": (192, 256),
        "tex2d": (192, 256),
        "pivot": (0.5, 0.75),
        "scale": 0.5,
    },
    "squareicon": {
        "sprite": (116, 116),
        "tex2d": (116, 116),
        "pivot": (0.5, 0.65),
        "scale": 0.5,
    },
}


def aspect_ratio(kind: str, w: int, h: int, clip: bool):
    std = metas[kind]["tex2d"]
    if round(std[0] / w * h) != std[1]:
        print(f"[WARNING] Bad aspect ratio {(w, h)}, expected {std}")
    if clip:
        w = round(w / std[0] * metas[kind]["sprite"][0])
    return w, h


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
        self.icons: dict[str, Image.Image] = {}

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

        face = "paintingface/" + os.path.basename(file).removesuffix("_n")
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
        [print(_) for _ in self.layers.values()]

        x_min, y_min = np.min([_.posMin for _ in self.layers.values()], 0)
        x_max, y_max = np.max([_.posMax for _ in self.layers.values()], 0)
        self.size = (round(x_max - x_min + 1), round(y_max - y_min + 1))
        self.bias = (-x_min, -y_min)

    def load_paintings(self, workload: dict[str, str]):
        def load(name: str, path: str):
            print("      ", path)
            layer = self.layers[name]
            x, y = np.add(layer.posMin, self.bias)
            w, h = layer.canvasSize
            sub = read_img(path).crop((x, y, x + w, y + h))
            self.repls[name] = sub.resize(layer.spriteSize)

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

    def clip_icons(self, workload: str):
        def clip(kind: str):
            x, y = np.subtract(layer.posMin, prefered.posMin) + np.multiply(layer.sizeDelta, 0.5)
            w, h = np.divide(metas[kind]["tex2d"], metas[kind]["scale"])
            px, py = metas[kind]["pivot"]
            # print(kind, prefered.name, x, y, w, h)
            img = full.crop((x - w * px, y - h * py, x + w * (1 - px), y + h * (1 - py)))
            tex2d_size = aspect_ratio(kind, *img.size, False)
            sprite_size = aspect_ratio(kind, *img.size, True)
            # print(kind, tex2d_size, sprite_size)
            sub = Image.new("RGBA", tex2d_size)
            sub.paste(img.crop((0, 0, *sprite_size)))
            path = os.path.join(os.path.dirname(self.meta), f"{kind}.png")
            sub.transpose(Image.FLIP_TOP_BOTTOM).save(path)
            output.append(path)

        layer = self.layers["face"]
        expands = [v for k, v in self.layers.items() if k != "face" if v.contain(*layer.box)]
        prefered = sorted(expands, key=lambda v: prod(v.canvasSize))[0]
        x, y = np.add(prefered.posMin, self.bias)
        w, h = prefered.canvasSize
        full = read_img(workload).crop((x, y, x + w, y + h)).resize(prefered.spriteSize)
        output = []

        tasks = [threading.Thread(target=clip, args=(k,)) for k in metas.keys()]
        [_.start() for _ in tasks]
        [_.join() for _ in tasks]

        return output
