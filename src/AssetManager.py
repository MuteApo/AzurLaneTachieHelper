import os
import re
import threading

import numpy as np
import UnityPy
from PIL import Image
from UnityPy.classes import AssetBundle, GameObject, RectTransform, Texture2D
from UnityPy.enums import ClassIDType

from .Data import MetaInfo
from .DecodeHelper import DecodeHelper
from .EncodeHelper import EncodeHelper
from .Layer import Layer
from .ui import IconPreset
from .utility import filter_env, prod, read_img
from .Vector import Vector2


class AssetManager:
    def __init__(self):
        self.init()

    def init(self):
        self.meta: MetaInfo = None
        self.deps: dict[str, str] = {}
        self.maps: dict[str, str] = {}
        self.layers: dict[str, Layer] = {}
        self.faces: dict[str, Image.Image] = {}
        self.icons: dict[str, Image.Image] = {}
        self.repls: dict[str, Image.Image] = {}

    @property
    def face_layer(self):
        return self.layers["face"]

    def decode(self, dir: str, dump: bool) -> str:
        return DecodeHelper.exec(dir, self.meta, self.layers, self.faces, dump)

    # def encode(self, dir: str, dump: bool) -> str:
    #     return EncodeHelper.exec(
    #         self.name,
    #         dir,
    #         self.meta,
    #         self.bias,
    #         self.maps,
    #         self.repls,
    #         self.icons,
    #         self.face_layer,
    #     )

    def analyze(self, file: str):
        self.init()

        base = os.path.basename(file).removesuffix("_n")

        env = UnityPy.load(file)
        abs: list[AssetBundle] = filter_env(env, AssetBundle)
        for dep in abs[0].m_Dependencies:
            path = os.path.join(os.path.dirname(file) + "/", dep)
            assert os.path.exists(path), f"Dependency not found: {dep}"
            self.deps[dep] = path
            env.load_file(path)

            if not dep.startswith("paintingface"):
                for x in env.files[path].container.values():
                    if x.type == ClassIDType.Sprite:
                        self.maps[dep] = x.read().name

        face = os.path.join("paintingface/", base)
        path = os.path.join(os.path.dirname(file) + "/", face)
        if os.path.exists(path):
            self.deps[face] = path
            env.load_file(path)
            self.faces = {
                x.name: x.image
                for x in filter_env(env, Texture2D)
                if re.match(r"^0|([1-9][0-9]*)$", x.name)
            }
        else:
            self.deps[face] = None

        for kind in ["shipyardicon", "squareicon", "herohrzicon"]:
            icon = os.path.join(kind + "/", base)
            path = os.path.join(os.path.dirname(file) + "/", icon)
            if os.path.exists(path):
                env.load_file(path)
                self.icons = {
                    kind: x.image
                    for x in filter_env(env, Texture2D)
                    if re.match(f"^(?i){base}$", x.name)
                }

        print("[INFO] Dependencies:")
        [print("      ", _) for _ in self.deps.keys()]

        base_go: GameObject = list(env.container.values())[0].read()
        base_rt: RectTransform = base_go.m_Transform.read()
        base_layer = Layer(base_rt)

        self.layers: dict[str, Layer] = base_layer.flatten()
        if "face" not in [x.name for x in self.layers.values()]:
            self.layers["face"] = base_layer.get_child("face")
        [print(_) for _ in self.layers.values()]

        x_min = min([_.posMin.X for _ in self.layers.values()])
        x_max = max([_.posMax.X for _ in self.layers.values()])
        y_min = min([_.posMin.Y for _ in self.layers.values()])
        y_max = max([_.posMax.Y for _ in self.layers.values()])
        size = Vector2(x_max - x_min, y_max - y_min).round()
        bias = Vector2(-x_min, -y_min)

        self.meta = MetaInfo(path, base_layer.name, size, bias)

    def load_paintings(self, workload: dict[str, str]):
        def load(name: str, path: str):
            print("      ", path)
            layer = self.layers[name]
            x, y = layer.posMin + self.bias
            w, h = layer.canvasSize
            sub = read_img(path).crop((x, y, x + w, y + h))
            self.repls[name] = sub.resize(layer.spriteSize.round().tuple())

        tasks = [threading.Thread(target=load, args=(k, v)) for k, v in workload.items()]
        [_.start() for _ in tasks]
        [_.join() for _ in tasks]

    def load_faces(self, workload: dict[int, str]):
        def load(name: str, path: str):
            print("      ", path)
            self.repls[name] = read_img(path)

        tasks = [threading.Thread(target=load, args=(k, v)) for k, v in workload.items()]
        [_.start() for _ in tasks]
        [_.join() for _ in tasks]

    def clip_icons(self, workload: str, presets: dict[str, IconPreset]):
        def clip(kind: str, preset: IconPreset):
            w, h = preset.tex2d / preset.scale
            x, y = center - Vector2(w, h) * preset.pivot

            path = os.path.join(os.path.dirname(self.meta), f"{kind}.png")
            img = full.rotate(preset.angle, center=(x + w / 2, y + h / 2))
            if kind == "shipyardicon":
                sub = img.copy()
                img = Image.new("RGBA", sub.size)
                img.paste(sub, (round(-10 / preset.scale), 0))
                data = np.array(img)
                data[..., :3] = 0
                data[..., 3] = np.where(data[..., 3] > 76, 76, data[..., 3])
                img = Image.fromarray(data)
                img.paste(sub, mask=sub)
            img.crop((x, y, x + w, y + h)).transpose(Image.FLIP_TOP_BOTTOM).save(path)
            output.append(path)

        full, center = self.prepare_icon(workload)
        output = []

        tasks = [threading.Thread(target=clip, args=(k, v)) for k, v in presets.items()]
        [_.start() for _ in tasks]
        [_.join() for _ in tasks]

        return output

    def prefered(self, layer: Layer) -> Layer:
        expands = [x for x in self.layers.values() if x.name != "face" and x.contain(*layer.box)]
        return sorted(expands, key=lambda v: prod(v.canvasSize))[0]

    def prepare_icon(self, file: str) -> tuple[Image.Image, Vector2]:
        prefered = self.prefered(self.face_layer)
        x, y = prefered.posMin + self.meta.bias
        w, h = prefered.canvasSize
        full = read_img(file).crop((x, y, x + w, y + h)).resize(prefered.spriteSize)
        center = self.face_layer.posMin - prefered.posMin + self.face_layer.sizeDelta / 2
        return full, center
