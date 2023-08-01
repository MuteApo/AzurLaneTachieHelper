import os
import re
import struct

import numpy as np
import UnityPy
from PIL import Image
from tqdm import tqdm
from UnityPy.classes import GameObject, Mesh, RectTransform, Sprite, Texture2D
from UnityPy.enums import ClassIDType, TextureFormat

from .TextureHelper import TextureHelper
from .utility import check_dir, filter_env

icons = ["shipyardicon", "squareicon", "herohrzicon"]
metas = {
    "sprite": {
        "herohrzicon": (272, 80),
        "shipyardicon": (192, 256),
        "squareicon": (116, 116),
    },
    "tex2d": {
        "herohrzicon": (360, 80),
        "shipyardicon": (192, 256),
        "squareicon": (116, 116),
    },
}


def aspect_ratio(kind: str, w: int, h: int, clip: bool):
    std = metas["tex2d"][kind]
    if round(std[0] / w * h) != std[1]:
        print(f"[WARNING] Bad aspect ratio {(w, h)}, expected {std}")
    if clip:
        w = round(w / std[0] * metas["sprite"][kind][0])
    return w, h


class EncodeHelper(TextureHelper):
    def exec(self, dir: str, is_clip: list[bool], replace_icon: bool) -> list[str]:
        print("[INFO] Encoding painting")
        valid = [os.path.basename(k) for k, v in self.maps.items() if v in self.repls]
        painting = [self._replace_painting(dir, x, self.repls) for x in tqdm(valid)]

        print("[INFO] Encoding paintingface")
        face = self._replace_face(dir, is_clip)

        icon = []
        if replace_icon:
            print("[INFO] Encoding icons")
            tmp = [self._replace_icon(dir, x) for x in icons]
            icon += [x for x in tmp if x is not None]

        return painting + face + icon

    def _replace_painting(self, dir: str, asset: str, img_dict: dict[str, Image.Image]) -> str:
        path = os.path.join(os.path.dirname(self.meta), "painting", asset)
        env = UnityPy.load(path)

        for _ in filter_env(env, Texture2D):
            tex2d: Texture2D = _.read()
            img = img_dict[tex2d.name.lower()]
            tex2d.m_Width, tex2d.m_Height = img.size
            tex2d.set_image(img.transpose(Image.FLIP_TOP_BOTTOM), TextureFormat.RGBA32)
            tex2d.save()

        for _ in filter_env(env, Mesh, False):
            mesh = _.read_typetree()

            mesh["m_SubMeshes"][0]["indexCount"] = 6
            mesh["m_SubMeshes"][0]["vertexCount"] = 4
            mesh["m_IndexBuffer"] = [0, 0, 1, 0, 2, 0, 2, 0, 3, 0, 0, 0]
            mesh["m_VertexData"]["m_VertexCount"] = 4
            w, h = img_dict[mesh["m_Name"].lower().split("-mesh")[0]].size
            buf = [0, 0, 0, 0, 0, 0, h, 0, 0, 1, w, h, 0, 1, 1, w, 0, 0, 1, 0]
            data_size = struct.pack(_.reader.endian + "f" * 20, *buf)
            mesh["m_VertexData"]["m_DataSize"] = memoryview(data_size)

            _.save_typetree(mesh)

        check_dir(dir, "output", "painting")
        output = os.path.join(dir, "output", "painting", asset)
        with open(output, "wb") as f:
            f.write(env.file.save("original"))

        return output

    def _replace_face(self, dir: str, is_clip: list[bool]) -> list[str]:
        if 1 not in self.repls:
            return []

        mod_wh = not all(is_clip)
        expands = [
            v for k, v in self.layers.items() if k != "face" if v.contain(*self.face_layer.box)
        ]
        prefered = sorted(expands, key=lambda v: v.sizeDelta[0] * v.sizeDelta[1])[0]

        path = os.path.join(os.path.dirname(self.meta), "paintingface", self.name.strip("_n"))
        env = UnityPy.load(path)

        x, y = np.add(self.face_layer.posMin, self.bias)
        w, h = self.face_layer.sizeDelta
        repls: dict[int, Image.Image] = {}
        for i, v in enumerate(tqdm(is_clip)):
            img = self.repls[i + 1]
            if not mod_wh:
                repls[i + 1] = img.crop((x, y, x + w, y + h))
            else:
                if v:
                    rgb = Image.new("RGBA", img.size)
                    rgb.paste(img.crop((x, y, x + w + 1, y + h + 1)), (round(x), round(y)))

                    a = Image.new("RGBA", img.size)
                    a.paste(img.crop((x + 1, y + 1, x + w, y + h)), (round(x + 1), round(y + 1)))

                    img = Image.merge("RGBA", [*rgb.split()[:3], a.split()[-1]])

                l, b, r, t = np.add(prefered.box, self.bias * 2)
                repls[i + 1] = img.crop((l, b, r, t))

        for _ in filter_env(env, Texture2D, False):
            tex2d: Texture2D = _.read()
            if re.match(r"^0|([1-9][0-9]*)$", tex2d.name):
                img = repls[eval(tex2d.name)]
                tex2d.m_Width, tex2d.m_Height = img.size
                tex2d.set_image(img.transpose(Image.FLIP_TOP_BOTTOM), TextureFormat.RGBA32)
                tex2d.save()

        for _ in filter_env(env, Sprite, False):
            sprite: Sprite = _.read()
            if re.match(r"^0|([1-9][0-9]*)$", sprite.name):
                size = repls[eval(sprite.name)].size
                sprite.m_Rect.width, sprite.m_Rect.height = size
                sprite.m_RD.textureRect.width, sprite.m_RD.textureRect.height = size
                sprite.save()

        check_dir(dir, "output", "paintingface")
        output = os.path.join(dir, "output", "paintingface", self.name.strip("_n"))
        with open(output, "wb") as f:
            f.write(env.file.save("original"))

        if not mod_wh:
            return [output]

        env = UnityPy.load(self.meta)
        base_go: GameObject = list(env.container.values())[0].read()
        base_rt: RectTransform = base_go.m_Transform.read()
        path_id = self.face_layer.pathId
        for _ in [__ for __ in base_rt.m_Children if __.path_id == path_id]:
            face = _.read_typetree()

            w, h = prefered.sizeDelta
            px, py = prefered.pivot
            x1, y1 = np.subtract(prefered.posPivot, self.face_layer.parent.posPivot)
            x2, y2 = np.subtract(np.add(prefered.posPivot, self.bias), self.face_layer.posAnchor)
            face["m_SizeDelta"] = {"x": w, "y": h}
            face["m_Pivot"] = {"x": px, "y": py}
            face["m_LocalPosition"] = {"x": x1, "y": y1, "z": 0.0}
            face["m_AnchoredPosition"] = {"x": x2, "y": y2}

            _.save_typetree(face)

        check_dir(dir, "output", "painting")
        meta = os.path.join(dir, "output", "painting", os.path.basename(self.meta))
        with open(meta, "wb") as f:
            f.write(env.file.save("original"))

        return [meta, output]

    def _replace_icon(self, dir: str, kind: str):
        ab = os.path.join(os.path.dirname(self.meta), kind, self.name)
        if not os.path.exists(ab):
            return

        env = UnityPy.load(ab)
        mod = False
        for v in env.container.values():
            sprite: Sprite = v.read()
            tex2d: Texture2D = sprite.m_RD.texture.read()

            for x in ["png", "jpg", "jpeg"]:
                src = os.path.join(os.path.dirname(self.meta), f"{kind}.{x}")
                if os.path.exists(src):
                    # print(f"       {src}")
                    img = Image.open(src)
                    tex2d_size = aspect_ratio(kind, *img.size, False)
                    sprite_size = aspect_ratio(kind, *img.size, True)
                    if sprite is not None:
                        sprite.m_Rect.width, sprite.m_Rect.height = tex2d_size
                        sprite.m_RD.textureRect.width, sprite.m_RD.textureRect.height = sprite_size
                        sprite.save()
                    tex2d.m_Width, tex2d.m_Height = tex2d_size
                    tex2d.set_image(img, target_format=TextureFormat.RGBA32)
                    tex2d.save()
                    mod = True
                    break

        if mod:
            check_dir(dir, "output", kind)
            outdir = os.path.join(dir, "output", kind)
            path = os.path.join(outdir, self.name)
            with open(path, "wb") as f:
                f.write(env.file.save("original"))
            return path
