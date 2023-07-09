import os
import re
import threading

import UnityPy
from PIL import Image
from UnityPy import Environment
from UnityPy.classes import AssetBundle, GameObject, RectTransform, Texture2D

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
        self.size: str = None
        self.deps: dict[str, str] = {}
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

        base_go: GameObject = list(env.container.values())[0].read()
        base_rt: RectTransform = base_go.m_Transform.read()
        base_layer = Layer(base_rt)
        self.layers[base_layer.name] = base_layer

        self.name = base_layer.name
        self.size = base_layer.sizeDelta

        for layers_rt in rt_filter_child(base_rt, "layers"):
            layers_layer = Layer(layers_rt, base_layer)
            for child_rt in [_.read() for _ in layers_rt.m_Children]:
                child_layer = Layer(child_rt, layers_layer)
                self.layers[child_layer.name] = child_layer

        face = "paintingface/" + os.path.basename(file).strip("_n")
        path = os.path.join(os.path.dirname(file) + "/", face)
        if os.path.exists(path):
            self.deps[face] = path
            env = UnityPy.load(path)
            for face_rt in rt_filter_child(base_rt, "face"):
                self.layers["face"] = Layer(face_rt, base_layer)
                self.faces |= {
                    eval(_.name): _.image.transpose(Image.FLIP_TOP_BOTTOM)
                    for _ in filter_env(env, Texture2D)
                    if re.match(r"^0|([1-9][0-9]*)", _.name)
                }
        else:
            self.deps[face] = None

        [print(_) for _ in self.layers.values()]

    def load_paintings(self, workload: dict[str, str]):
        def load(name: str, path: str):
            print("      ", path)
            x, y = self.layers[name].offset
            w, h = self.layers[name].sizeDelta
            box = min(x + w, self.size[0]), min(y + h, self.size[1])
            sub = Image.new("RGBA", (w, h))
            sub.paste(read_img(path).crop((x, y, *box)))
            self.repls[name] = sub.resize(self.layers[name].rawSpriteSize)

        tasks = [threading.Thread(target=load, args=(k, v)) for k, v in workload.items()]
        [_.start() for _ in tasks]
        [_.join() for _ in tasks]

    def load_faces(self, dir: str):
        def load(name: str, path: str):
            print("      ", path)
            x, y = self.layers["face"].offset
            w, h = self.layers["face"].sizeDelta
            img = read_img(path)
            if "+" in name:
                full = img
            else:
                rgb = Image.new("RGBA", img.size)
                rgb.paste(img.crop((x, y, x + w + 1, y + h + 1)), (x, y))
                r, g, b, _ = rgb.split()

                alpha = Image.new("RGBA", img.size)
                alpha.paste(img.crop((x + 1, y + 1, x + w, y + h)), (x + 1, y + 1))
                _, _, _, a = alpha.split()

                full = Image.merge("RGBA", [r, g, b, a])
            self.repls[eval(name.strip("+-"))] = full

        for path, _, files in os.walk(dir):
            imgs = {os.path.splitext(_)[0]: os.path.join(path, _) for _ in files}
            tasks = [
                threading.Thread(target=load, args=(k, v))
                for k, v in imgs.items()
                if re.match(r"^0|([1-9][0-9]*)", k)
            ]
            [_.start() for _ in tasks]
            [_.join() for _ in tasks]
