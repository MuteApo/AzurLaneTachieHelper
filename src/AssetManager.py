import os
import re
import threading

import UnityPy
from PIL import Image
from UnityPy.classes import AssetBundle, GameObject, RectTransform, Texture2D
from UnityPy.enums import ClassIDType

from .IconViewer import IconPreset
from .Layer import Layer
from .utility import filter_env, prod, read_img
from .Vector import Vector2


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
        self.icons: dict[str, Image.Image] = {}
        self.repls: dict[str | int, Image.Image] = {}

    @property
    def face_layer(self):
        return self.layers["face"]

    def analyze(self, file: str):
        self.init()

        self.meta = file
        base = os.path.basename(file).removesuffix("_n")

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

        face = os.path.join("paintingface/", base)
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

        for kind in ["shipyardicon", "squareicon", "herohrzicon"]:
            icon = os.path.join(kind + "/", base)
            path = os.path.join(os.path.dirname(file) + "/", icon)
            if os.path.exists(path):
                env.load_file(path)
                self.icons |= {
                    kind: _.image
                    for _ in filter_env(env, Texture2D)
                    if re.match(f"^{base}$", _.name)
                }
            else:
                self.icons[kind] = None
        print(self.icons)

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

    def clip_icons(self, workload: str, presets: dict[str, IconPreset]):
        def clip(kind: str, preset: IconPreset):
            size = preset.tex2d / preset.scale
            pivot = preset.pivot
            x0, y0 = center - size * pivot
            x1, y1 = center + size * (Vector2.one() - pivot)

            path = os.path.join(os.path.dirname(self.meta), f"{kind}.png")
            full.crop((x0, y0, x1, y1)).transpose(Image.FLIP_TOP_BOTTOM).save(path)
            output.append(path)

        full, center = self.prepare_icon(workload)
        output = []

        tasks = [threading.Thread(target=clip, args=(k, v)) for k, v in presets.items()]
        [_.start() for _ in tasks]
        [_.join() for _ in tasks]

        return output

    def prefered(self, layer: Layer) -> Layer:
        expands = [v for k, v in self.layers.items() if k != "face" if v.contain(*layer.box)]
        return sorted(expands, key=lambda v: prod(v.canvasSize))[0]

    def prepare_icon(self, file: str) -> tuple[Image.Image, Vector2]:
        prefered = self.prefered(self.face_layer)
        x, y = prefered.posMin + self.bias
        w, h = prefered.canvasSize
        full = read_img(file).crop((x, y, x + w, y + h)).resize(prefered.spriteSize)
        center = self.face_layer.posMin - prefered.posMin + self.face_layer.sizeDelta / 2
        return full, center
