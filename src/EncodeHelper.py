import os
import struct

import UnityPy
from PIL import Image
from UnityPy.classes import Mesh, Texture2D
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

    def _replace_painting(self, dir, asset, img_dict):
        path = os.path.join(os.path.dirname(self.meta), "painting", asset)
        env = UnityPy.load(path)

        for _ in filter_env(env, Texture2D):
            tex2d: Texture2D = _.read()
            img = img_dict[tex2d.name.lower()]
            tex2d.m_Width, tex2d.m_Height = img.size
            tex2d.set_image(
                img.transpose(Image.FLIP_TOP_BOTTOM),
                target_format=TextureFormat.RGBA32,
                in_cab=True,
            )
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
            f.write(env.file.save("lz4"))

        return output

    def _replace_face(self, dir: str):
        if 1 not in self.repls:
            return []

        path = os.path.join(os.path.dirname(self.meta), "paintingface", self.name.strip("_n"))
        env = UnityPy.load(path)

        for _ in filter_env(env, Texture2D):
            tex2d: Texture2D = _.read()
            tex2d.set_image(
                self.repls[eval(tex2d.name)].transpose(Image.FLIP_TOP_BOTTOM),
                target_format=TextureFormat.RGBA32,
                in_cab=True,
            )
            tex2d.save()

        check_dir(dir, "output", "paintingface")
        output = os.path.join(dir, "output", "paintingface", self.name.strip("_n"))
        with open(output, "wb") as f:
            f.write(env.file.save("lz4"))

        return [output]
