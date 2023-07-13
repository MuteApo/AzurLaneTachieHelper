import os
import re
import struct

import numpy as np
import UnityPy
from PIL import Image
from UnityPy.classes import GameObject, Mesh, RectTransform, Sprite, Texture2D
from UnityPy.enums import TextureFormat

from .TextureHelper import TextureHelper
from .utility import check_dir, filter_env


class EncodeHelper(TextureHelper):
    def exec(self, dir: str) -> list[str]:
        painting = [
            self._replace_painting(dir, x + "_tex", self.repls)
            for x in self.layers.keys()
            if x in self.repls
        ]
        face = self._replace_face(dir)
        return painting + face

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

    def _replace_face(self, dir: str) -> list[str]:
        if 1 not in self.repls:
            return []

        path = os.path.join(os.path.dirname(self.meta), "paintingface", self.name.strip("_n"))
        env = UnityPy.load(path)

        mod_wh = None
        for _ in filter_env(env, Texture2D, False):
            tex2d: Texture2D = _.read()
            if re.match(r"^0|([1-9][0-9]*)", tex2d.m_Name):
                img = self.repls[eval(tex2d.m_Name)]
                w0, h0 = self.layers["face"].sizeDelta
                if w0 != img.size[0] or h0 != img.size[1]:
                    mod_wh = np.array(img.size).astype(np.float32)
                tex2d.m_Width, tex2d.m_Height = img.size
                tex2d.set_image(img.transpose(Image.FLIP_TOP_BOTTOM), TextureFormat.RGBA32)
                tex2d.save()

        for _ in filter_env(env, Sprite, False):
            sprite: Sprite = _.read()
            if re.match(r"^0|([1-9][0-9]*)", sprite.name):
                size = self.repls[eval(sprite.name)].size
                sprite.m_Rect.width, sprite.m_Rect.height = size
                sprite.m_RD.textureRect.width, sprite.m_RD.textureRect.height = size
                sprite.save()

        check_dir(dir, "output", "paintingface")
        output = os.path.join(dir, "output", "paintingface", self.name.strip("_n"))
        with open(output, "wb") as f:
            f.write(env.file.save("original"))

        if mod_wh is None:
            return [output]

        env = UnityPy.load(self.meta)
        base_go: GameObject = list(env.container.values())[0].read()
        base_rt: RectTransform = base_go.m_Transform.read()
        path_id = self.layers["face"].pathId
        for _ in [__ for __ in base_rt.m_Children if __.path_id == path_id]:
            face = _.read_typetree()

            w, h = mod_wh
            pivot = self.layers["face"].pivot * mod_wh
            x1, y1 = pivot - self.layers["face"].parent.posPivot
            x2, y2 = pivot - self.layers["face"].posAnchor
            face["m_SizeDelta"] = {"x": w, "y": h}
            face["m_LocalPosition"] = {"x": x1, "y": y1, "z": 0.0}
            face["m_AnchoredPosition"] = {"x": x2, "y": y2}

            _.save_typetree(face)

        check_dir(dir, "output", "painting")
        meta = os.path.join(dir, "output", "painting", os.path.basename(self.meta))
        with open(meta, "wb") as f:
            f.write(env.file.save("original"))

        return [output, meta]
