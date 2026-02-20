import os
import pprint
import re
from concurrent.futures import ThreadPoolExecutor
from stat import filemode

import numpy as np
import UnityPy
from PIL import Image
from UnityPy.classes import GameObject, MonoBehaviour, Texture2D
from UnityPy.enums import ClassIDType

from ..base import Config
from ..base.Data import IconPreset, IconPresets, MetaInfo
from ..base.Layer import FaceLayer, IconLayer, Layer, prefered_layer
from ..base.Vector import Vector2
from ..logger import logger
from ..utility import open_and_transpose
from .AdbHelper import AdbHelper
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

    def decode(self, dir: str) -> str:
        faces = {int(k): v for k, v in self.faces.items()}
        psd = DecodeHelper.exec(self.layers, faces)
        path = os.path.join(dir, f"{self.meta.name}.psd")
        if os.path.exists(path):
            old = [x for x in os.listdir(dir) if re.match(rf"{self.meta.name}\.bak_\d+\.psd", x)]
            num = sorted([eval(re.search(r"bak_(\d+).psd", x).group(1)) for x in old])
            last = 1 if old == [] else num[-1] + 1
            os.rename(path, os.path.join(dir, f"{self.meta.name}.bak_{last}.psd"))
        with open(path, "wb") as f:
            psd.write(f)
        return path

    def encode(self, dir: str) -> str:
        return EncodeHelper.exec(dir, self.layers, self.faces, self.icons)

    def get_dependency(self, file: str) -> list[str]:
        if not os.path.exists("dependencies"):
            AdbHelper.pull("dependencies", add_prefix=True)
        env = UnityPy.load("dependencies")
        mb: MonoBehaviour = [x.read() for x in env.objects if x.type == ClassIDType.MonoBehaviour][0]
        idx = mb.m_Keys.index(f"painting/{os.path.basename(file)}")
        return mb.m_Values[idx].m_Dependencies

    def analyze(self, file: str):
        self.init()

        self.deps = self.get_dependency(file)
        logger.attr("Dependencies", ", ".join(self.deps))

        env = UnityPy.load(file)
        for dep in self.deps:
            path = os.path.join(os.path.dirname(file) + "/", dep)
            assert os.path.exists(path), f"Dependency not found: {dep}"
            env.load_file(path)

        file_map = {
            os.path.basename(x)[:-4].lower(): k
            for k, v in env.files.items()
            for x in v.container.keys()
            if x.endswith(".png")
        }

        base_go: GameObject = [x.read() for x in env.container.values() if x.type == ClassIDType.GameObject][0]
        base_layer = Layer(base_go.m_Component[0].component)

        self.layers = base_layer.flatten()
        if "face" not in [x.name for x in self.layers.values()]:
            self.layers["face"] = base_layer.get_child("face")
        for k in set(self.layers.keys()) - {"face"}:
            if self.layers[k].texture2D.m_Name.lower() == "uisprite":
                self.layers.pop(k)
        [logger.attr(layer.__repr__(), layer.__str__()) for layer in self.layers.values()]

        x_min = min([_.posMin.X for _ in self.layers.values()])
        x_max = max([_.posMax.X for _ in self.layers.values()])
        y_min = min([_.posMin.Y for _ in self.layers.values()])
        y_max = max([_.posMax.Y for _ in self.layers.values()])
        size = Vector2(x_max - x_min, y_max - y_min)
        bias = Vector2(-x_min, -y_min)

        self.meta = MetaInfo(file, base_layer.name, size, bias)

        base = os.path.basename(file).removesuffix("_n")
        path = os.path.join(os.path.dirname(file), "paintingface", base)
        if os.path.exists(path):
            env = UnityPy.load(path)
            tex2ds: list[Texture2D] = [x.read() for x in env.objects if x.type == ClassIDType.Texture2D]
            self.faces = {x.m_Name: FaceLayer(self.meta, x, path) for x in tex2ds}
            self.faces = {k: v for k, v in sorted(self.faces.items(), key=lambda x: int(x[0]))}

        for k, v in self.layers.items():
            v.meta = self.meta
            if k != "face":
                v.path = file_map[v.texture2D.m_Name.lower()]
                if Config.get_face_extension(self.meta.name_stem, k) is None:
                    Config.set_face_extension(self.meta.name_stem, k, [0] * 4)

        presets = IconPresets()
        for k, v in presets.to_dict().items():
            path = os.path.join(os.path.dirname(file), k, base)
            if not os.path.exists(path):
                path += ".ys"
            if os.path.exists(path):
                env = UnityPy.load(path)
                for x in env.objects:
                    if x.type == ClassIDType.Texture2D:
                        tex2d: Texture2D = x.read()
                        if re.match(f"(?i)^{base}$", tex2d.m_Name):
                            icon_layer = IconLayer(self.meta, tex2d, path)
                self.icons[k] = icon_layer

    def clip_icons(self, workload: str, presets: IconPresets) -> list[str]:
        full, center = self.prepare_icon(workload)

        def clip(kind: str, preset: IconPreset):
            w, h = preset.size / preset.scale
            x, y = center - Vector2(w, h) * preset.pivot

            path = os.path.join(os.path.dirname(self.meta.path), f"{kind}.png")
            img = full.rotate(preset.angle, center=(x + w / 2, y + h / 2))
            if kind == "shipyardicon":
                sub = img.copy()
                img = Image.new("RGBA", sub.size)
                img.paste(sub, (round(-10 / preset.scale), 0))
                data = np.array(img)
                data[..., :3] = 0
                data[..., 3] = np.where(data[..., 3] > 76, 76, data[..., 3])
                img = Image.fromarray(data)
                img.alpha_composite(sub)
            img.crop((x, y, x + w, y + h)).transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(path)

            return path

        with ThreadPoolExecutor(max_workers=8) as executor:
            output = executor.map(clip, presets.to_dict().keys(), presets.to_dict().values())

        return list(output)

    def prepare_icon(self, file: str) -> tuple[Image.Image, Vector2]:
        prefered = prefered_layer(self.layers, self.face_layer)
        full = open_and_transpose(file).crop(prefered.box)
        center = self.face_layer.posMin - prefered.posMin + self.face_layer.sizeDelta / 2
        return full.resize(prefered.sizeDelta.round()), center
