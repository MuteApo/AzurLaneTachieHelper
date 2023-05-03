import os
import struct

import UnityPy
from PIL import Image
from UnityPy.classes import Mesh, Texture2D
from UnityPy.enums import TextureFormat

from .TextureHelper import TextureHelper
from .utility import check_dir, filter_env, read_img


class EncodeHelper(TextureHelper):
    def load(self, name: str, path: str):
        x, y = self.metas[name]["Offset"]
        w, h = self.metas[name]["SizeDelta"]
        self.metas[name] |= {
            "rep": read_img(path).resize(
                self.metas[name]["RawSpriteSize"],
                Image.Resampling.LANCZOS,
                (x, y, x + w, y + h),
            )
        }

    def exec(self, dir: str):
        return "\n".join(
            [
                self._replace(dir, "painting/", _ + "_tex", {_: self.metas[_]["rep"]})
                for _ in self.metas.keys()
            ]
        )

    def _replace(self, dir, folder, asset, img_dict):
        env = UnityPy.load(os.path.join(dir, folder, asset))

        for _ in filter_env(env, Texture2D):
            tex2d: Texture2D = _.read()
            img = img_dict[tex2d.name]
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

            w, h = img_dict[mesh["m_Name"].split("-mesh")[0]].size
            buf = [0, 0, 0, 0, 0, 0, h, 0, 0, 1, w, h, 0, 1, 1, w, 0, 0, 1, 0]
            data_size = struct.pack(_.reader.endian + "f" * 20, *buf)
            mesh["m_VertexData"]["m_DataSize"] = memoryview(data_size)

            _.save_typetree(mesh)

        check_dir(dir, "output", folder)
        output = os.path.join(dir, "output/", folder, asset)
        with open(output, "wb") as f:
            f.write(env.file.save("lz4"))

        return output
