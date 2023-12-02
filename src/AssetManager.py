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
from .Layer import Layer, PseudoLayer
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
        self.faces: dict[str, PseudoLayer] = {}
        self.icons: dict[str, PseudoLayer] = {}

    @property
    def face_layer(self):
        return self.layers["face"]

    def decode(self, dir: str, dump: bool) -> str:
        return DecodeHelper.exec(dir, self.meta, self.layers, self.faces, dump)

    def encode(self, dir: str) -> str:
        faces = {int(k): v for k, v in self.faces.items()}
        return EncodeHelper.exec(dir, self.layers, faces, self.icons)

    def analyze(self, file: str):
        self.init()

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

        self.meta = MetaInfo(file, base_layer.name, size, bias)

        for k, v in self.layers.items():
            v.meta = self.meta
            if k != "face":
                v.path = self.deps[f"painting/{v.texture2D.name}_tex"]

        base = os.path.basename(file).removesuffix("_ex").removesuffix("_n")
        face = os.path.join("paintingface/", base)
        path = os.path.join(os.path.dirname(file) + "/", face)
        if os.path.exists(path):
            env.load_file(path)
            self.faces = {
                x.name: PseudoLayer(x.image.transpose(Image.FLIP_TOP_BOTTOM))
                for x in filter_env(env, Texture2D)
                if re.match(r"^0|([1-9][0-9]*)$", x.name)
            }

        for kind in ["shipyardicon", "squareicon", "herohrzicon"]:
            icon = os.path.join(kind + "/", base)
            path = os.path.join(os.path.dirname(file) + "/", icon)
            if os.path.exists(path):
                env.load_file(path)
                self.icons |= {
                    kind: PseudoLayer(x.image.transpose(Image.FLIP_TOP_BOTTOM))
                    for x in filter_env(env, Texture2D)
                    if re.match(f"^(?i){base}$", x.name)
                }

    def clip_icons(self, workload: str, presets: dict[str, IconPreset]) -> list[str]:
        def clip(kind: str, preset: IconPreset):
            w, h = preset.tex2d / preset.scale
            x, y = center - Vector2(w, h) * preset.pivot

            path = os.path.join(os.path.dirname(self.meta.path), f"{kind}.png")
            img = full.rotate(preset.angle, center=(x + w / 2, y + h / 2))
            if kind == "shipyardicon":
                sub = img.copy()
                img = Image.new("RGBA", sub.size)
                img.paste(sub, (round(-9 / preset.scale), 0))
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
