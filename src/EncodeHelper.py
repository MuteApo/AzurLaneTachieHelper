import os
import re
import struct

import numpy as np
import UnityPy
from PIL import Image
from tqdm import tqdm
from UnityPy.classes import GameObject, Mesh, RectTransform, Sprite, Texture2D
from UnityPy.enums import TextureFormat

from .TextureHelper import TextureHelper
from .utility import check_dir, filter_env


class EncodeHelper(TextureHelper):
    def exec(self, dir: str, clip: list[bool]) -> list[str]:
        print("[INFO] Encoding painting")
        painting = []
        for x in tqdm([x + "_tex" for x in self.layers.keys() if x in self.repls]):
            painting += [self._replace_painting(dir, x, self.repls)]

        print("[INFO] Encoding paintingface")
        face = self._replace_face(dir, clip)

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

    def _replace_face(self, dir: str, clip: list[bool]) -> list[str]:
        if 1 not in self.repls:
            return []

        path = os.path.join(os.path.dirname(self.meta), "paintingface", self.name.strip("_n"))
        env = UnityPy.load(path)

        mod_wh = not all(clip)
        if mod_wh:
            wh = np.array(self.size).astype(np.float32)

        repls = {}
        x, y = np.add(self.layers["face"].posMin, self.bias)
        w, h = self.layers["face"].sizeDelta
        for i, v in enumerate(tqdm(clip)):
            img = self.repls[i + 1]
            if not mod_wh:
                repls[i + 1] = img.crop((x, y, x + w, y + h))
            elif not v:
                repls[i + 1] = img
            else:
                rgb = Image.new("RGBA", img.size)
                rgb.paste(img.crop((x, y, x + w + 1, y + h + 1)), (round(x), round(y)))
                r, g, b, _ = rgb.split()

                alpha = Image.new("RGBA", img.size)
                alpha.paste(img.crop((x + 1, y + 1, x + w, y + h)), (round(x + 1), round(y + 1)))
                _, _, _, a = alpha.split()

                repls[i + 1] = Image.merge("RGBA", [r, g, b, a])

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
        path_id = self.layers["face"].pathId
        for _ in [__ for __ in base_rt.m_Children if __.path_id == path_id]:
            face = _.read_typetree()

            pivot = self.layers["face"].pivot * wh
            x1, y1 = pivot - self.layers["face"].parent.posPivot
            x2, y2 = pivot - self.layers["face"].posAnchor
            face["m_SizeDelta"] = {"x": wh[0], "y": wh[1]}
            face["m_LocalPosition"] = {"x": x1, "y": y1, "z": 0.0}
            face["m_AnchoredPosition"] = {"x": x2, "y": y2}

            _.save_typetree(face)

        check_dir(dir, "output", "painting")
        meta = os.path.join(dir, "output", "painting", os.path.basename(self.meta))
        with open(meta, "wb") as f:
            f.write(env.file.save("original"))

        return [meta, output]
