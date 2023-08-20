import os
import re
import struct

import UnityPy
from PIL import Image
from tqdm import tqdm
from UnityPy.classes import Mesh, Sprite, Texture2D
from UnityPy.enums import TextureFormat

from .TextureHelper import TextureHelper
from .utility import check_dir, filter_env


class EncodeHelper(TextureHelper):
    def exec(self, dir: str, replace_icon: bool, adv_mode: bool, is_clip: list[bool]) -> list[str]:
        painting = []
        valid = [os.path.basename(k) for k, v in self.maps.items() if v in self.repls]
        if valid != []:
            print("[INFO] Encoding painting")
            painting += [self._replace_painting(dir, x, self.repls) for x in tqdm(valid)]

        face = []
        if 1 in self.repls:
            print("[INFO] Encoding paintingface")
            face += self._replace_face(dir, adv_mode, is_clip)

        icon = []
        if replace_icon and self.icons != []:
            print("[INFO] Encoding icons")
            icon += [self._replace_icon(dir, x) for x in tqdm(self.icons.keys())]

        return painting + face + icon

    def _replace_painting(self, dir: str, asset: str, img_dict: dict[str, Image.Image]) -> str:
        path = os.path.join(os.path.dirname(self.meta), "painting", asset)
        env = UnityPy.load(path)

        for _ in filter_env(env, Texture2D):
            tex2d: Texture2D = _.read()
            img = img_dict[tex2d.name]
            tex2d.m_Width, tex2d.m_Height = img.size
            tex2d.set_image(img.transpose(Image.FLIP_TOP_BOTTOM), TextureFormat.RGBA32)
            tex2d.save()

        for _ in filter_env(env, Mesh, False):
            mesh = _.read_typetree()

            mesh["m_SubMeshes"][0]["indexCount"] = 6
            mesh["m_SubMeshes"][0]["vertexCount"] = 4
            mesh["m_IndexBuffer"] = [0, 0, 1, 0, 2, 0, 2, 0, 3, 0, 0, 0]
            mesh["m_VertexData"]["m_VertexCount"] = 4
            w, h = img_dict[mesh["m_Name"].split("-mesh")[0]].size
            buf = [0, 0, 0, 0, 0, 0, h, 0, 0, 1, w, h, 0, 1, 1, w, 0, 0, 1, 0]
            data_size = struct.pack(_.reader.endian + "f" * 20, *buf)
            mesh["m_VertexData"]["m_DataSize"] = memoryview(data_size)

            _.save_typetree(mesh)

        check_dir(dir, "output", "painting")
        output = os.path.join(dir, "output", "painting", asset)
        with open(output, "wb") as f:
            f.write(env.file.save("original"))

        return output

    def _replace_face(self, dir: str, adv_mode: bool, is_clip: list[bool]) -> list[str]:
        layer = self.face_layer
        prefered = self.asset_manager.prefered(layer)

        path = os.path.join(
            os.path.dirname(self.meta), "paintingface", self.name.removesuffix("_n")
        )
        env = UnityPy.load(path)

        layer = self.face_layer
        repls: dict[int, Image.Image] = {}
        for i, v in enumerate(tqdm(is_clip)):
            x, y = layer.posMin + self.bias
            w, h = layer.sizeDelta
            img = self.repls[i + 1]
            if not adv_mode:
                repls[i + 1] = img.crop((x, y, x + w, y + h))
            else:
                if v:
                    rgb = Image.new("RGBA", img.size)
                    rgb.paste(img.crop((x, y, x + w + 1, y + h + 1)), (round(x), round(y)))

                    a = Image.new("RGBA", img.size)
                    a.paste(img.crop((x + 1, y + 1, x + w, y + h)), (round(x + 1), round(y + 1)))

                    img = Image.merge("RGBA", [*rgb.split()[:3], a.split()[-1]])

                x, y = prefered.posMin + self.bias
                w, h = prefered.canvasSize
                repls[i + 1] = img.crop((x, y, x + w, y + h))

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
        output = os.path.join(dir, "output", "paintingface", self.name.removesuffix("_n"))
        with open(output, "wb") as f:
            f.write(env.file.save("original"))

        if not adv_mode:
            return [output]

        env = UnityPy.load(self.meta)
        cab = list(env.cabs.values())[0]
        face_rt = cab.objects[layer.pathId]
        face = face_rt.read_typetree()
        w, h = prefered.canvasSize
        px, py = prefered.pivot
        fix = (prefered.canvasSize - prefered.sizeDelta) * prefered.pivot
        x1, y1 = (prefered.posPivot - layer.parent.posPivot) + fix
        x2, y2 = (prefered.posPivot - layer.posAnchor) + fix + self.bias
        face["m_SizeDelta"] = {"x": w, "y": h}
        face["m_Pivot"] = {"x": px, "y": py}
        face["m_LocalPosition"] = {"x": x1, "y": y1, "z": 0.0}
        face["m_AnchoredPosition"] = {"x": x2, "y": y2}
        face_rt.save_typetree(face)

        check_dir(dir, "output", "painting")
        meta = os.path.join(dir, "output", "painting", os.path.basename(self.meta))
        with open(meta, "wb") as f:
            f.write(env.file.save("original"))

        return [meta, output]

    def _replace_icon(self, dir: str, kind: str):
        if kind not in self.icons:
            return

        ab = os.path.join(os.path.dirname(self.meta), kind, self.name)
        if not os.path.exists(ab):
            return

        env = UnityPy.load(ab)
        mod = False
        for v in env.container.values():
            img = self.icons[kind]
            sprite: Sprite = v.read()
            tex2d: Texture2D = sprite.m_RD.texture.read()
            tex2d.set_image(img.resize(tex2d.image.size), TextureFormat.RGBA32)
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
