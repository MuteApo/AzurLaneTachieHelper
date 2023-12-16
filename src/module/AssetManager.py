import os
import re
import threading

import numpy as np
import UnityPy
from PIL import Image
from UnityPy.classes import AssetBundle, GameObject, RectTransform, Texture2D

from ..base import FaceLayer, IconLayer, IconPreset, Layer, MetaInfo, Vector2
from ..utility import filter_env
from .DecodeHelper import DecodeHelper
from .EncodeHelper import EncodeHelper


class AssetManager:
    def __init__(self):
        self.init()

    def init(self):
        self.meta: MetaInfo = None
        self.deps: dict[str, str] = {}
        self.layers: dict[str, Layer] = {}
        self.faces: dict[str, FaceLayer] = {}
        self.icons: dict[str, IconLayer] = {}

    @property
    def face_layer(self):
        return self.layers["face"]

    def decode(self, dir: str, dump: bool) -> str:
        faces = {int(k): v for k, v in self.faces.items()}
        psd = DecodeHelper.exec(dir, self.layers, faces, dump)
        path = os.path.join(dir, self.meta.name + ".psd")
        with open(path, "wb") as f:
            psd.write(f)

        return path

    def encode(self, dir: str) -> str:
        return EncodeHelper.exec(dir, self.layers, self.faces, self.icons)

    def analyze(self, file: str):
        self.init()

        env = UnityPy.load(file)
        abs: list[AssetBundle] = filter_env(env, AssetBundle)
        for dep in abs[0].m_Dependencies:
            path = os.path.join(os.path.dirname(file) + "/", dep)
            assert os.path.exists(path), f"Dependency not found: {dep}"
            self.deps[dep] = path
            env.load_file(path)

        print("[INFO] Dependencies:")
        [print("      ", _) for _ in self.deps.keys()]

        base_go: GameObject = list(env.container.values())[0].read()
        base_rt: RectTransform = base_go.m_Transform.read()
        base_layer = Layer(base_rt)

        self.layers: dict[str, Layer] = base_layer.flatten()
        if "face" not in [x.name for x in self.layers.values()]:
            self.layers["face"] = base_layer.get_child("face")
        [print(_) for _ in self.layers.values()]

        base = os.path.basename(file).removesuffix("_ex").removesuffix("_n")
        path = os.path.join(os.path.dirname(file), "paintingface", base)
        if os.path.exists(path):
            env.load_file(path)
            self.faces = {
                x.name: FaceLayer(x.name, path, x.image.transpose(Image.FLIP_TOP_BOTTOM))
                for x in filter_env(env, Texture2D)
                if re.match(r"^0|([1-9]\d*)$", x.name)
            }

        for kind in ["shipyardicon", "squareicon", "herohrzicon"]:
            path = os.path.join(os.path.dirname(file), kind, base)
            if os.path.exists(path):
                env.load_file(path)
                self.icons |= {
                    kind: IconLayer(kind, path, x.image.transpose(Image.FLIP_TOP_BOTTOM))
                    for x in filter_env(env, Texture2D)
                    if re.match(f"^(?i){base}$", x.name)
                }

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
        return sorted(expands, key=lambda v: v.canvasSize.prod())[0]

    def prepare_icon(self, file: str) -> tuple[Image.Image, Vector2]:
        prefered = self.prefered(self.face_layer)
        x, y = prefered.posMin + self.meta.bias
        w, h = prefered.canvasSize
        full = Image.open(file).transpose(Image.FLIP_TOP_BOTTOM).crop((x, y, x + w, y + h))
        center = self.face_layer.posMin - prefered.posMin + self.face_layer.sizeDelta / 2
        return full.resize(prefered.spriteSize), center
