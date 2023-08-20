import os
import re
import threading

import UnityPy
from PIL import Image
from UnityPy.classes import AssetBundle, GameObject, RectTransform, Texture2D
from UnityPy.enums import ClassIDType

from .Layer import Layer
from .utility import filter_env, prod, read_img
from .Vector import Vector2

metas = {
    "herohrzicon": {
        "sprite": Vector2(272, 80),
        "tex2d": Vector2(360, 80),
        "pivot": Vector2(0.35, 0.5),
        "scale": 0.6,
    },
    "shipyardicon": {
        "sprite": Vector2(192, 256),
        "tex2d": Vector2(192, 256),
        "pivot": Vector2(0.5, 0.7),
        "scale": 0.7,
    },
    "squareicon": {
        "sprite": Vector2(116, 116),
        "tex2d": Vector2(116, 116),
        "pivot": Vector2(0.5, 0.55),
        "scale": 0.6,
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
        self.size: Vector2 = None
        self.bias: Vector2 = None
        self.deps: dict[str, str] = {}
        self.maps: dict[str, str] = {}
        self.layers: dict[str, Layer] = {}
        self.faces: dict[int, Image.Image] = {}
        self.repls: dict[str | int, Image.Image] = {}
        self.icons: dict[str, Image.Image] = {}

    def analyze(self, file: str):
        self.init()

        self.meta = file

        env = UnityPy.load(file)
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

        x_min = min([_.posMin.X for _ in self.layers.values()])
        x_max = max([_.posMax.X for _ in self.layers.values()])
        y_min = min([_.posMin.Y for _ in self.layers.values()])
        y_max = max([_.posMax.Y for _ in self.layers.values()])
        self.size = Vector2(x_max - x_min + 1, y_max - y_min + 1)
        self.bias = Vector2(-x_min, -y_min)

    def load_paintings(self, workload: dict[str, str]):
        def load(name: str, path: str):
            print("      ", path)
            layer = self.layers[name]
            x, y = layer.posMin + self.bias
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
            center = layer.posMin - prefered.posMin + layer.sizeDelta / 2
            size = metas[kind]["tex2d"] / metas[kind]["scale"]
            pivot = metas[kind]["pivot"]
            x0, y0 = center - size * pivot
            x1, y1 = center + size * (Vector2.one() - pivot)
            # print(kind, prefered.name, x, y, w, h)
            img = full.crop((x0, y0, x1, y1))
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
        x, y = prefered.posMin + self.bias
        w, h = prefered.canvasSize
        full = read_img(workload).crop((x, y, x + w, y + h)).resize(prefered.spriteSize)
        output = []

        tasks = [threading.Thread(target=clip, args=(k,)) for k in metas.keys()]
        [_.start() for _ in tasks]
        [_.join() for _ in tasks]

        return output
