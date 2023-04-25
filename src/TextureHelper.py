import os
import UnityPy
from PIL import Image
from UnityPy.classes import Mesh, Texture2D
from UnityPy.enums import TextureFormat

from .utility import check_dir
import struct


class TextureHelper:
    def __init__(self):
        self.mesh_obj = {}
        self.enc_img = {}
        self.dec_img = {}
        self.whs = {}

    def _enc_img(self, file: str) -> str:
        return file + "-enc"

    def _dec_img(self, file: str) -> str:
        return file + "-dec"

    def _mesh_obj(self, file: str) -> str:
        return file + "-mesh"

    def _replace(self, dir, folder, asset, img_dict):
        asset_path = os.path.join(dir, folder, asset)
        assert os.path.exists(asset_path), f"file {asset_path} not found"

        env = UnityPy.load(asset_path)
        for _ in env.objects:
            if _.type.name == "Texture2D":
                tex2d: Texture2D = _.read()
                img = img_dict[tex2d.name]
                tex2d.m_Width = img.size[0]
                tex2d.m_Height = img.size[1]
                tex2d.set_image(
                    img_dict[tex2d.name].transpose(Image.FLIP_TOP_BOTTOM),
                    target_format=TextureFormat.RGBA32,
                    in_cab=True,
                )
                tex2d.save()
            elif _.type.name == "Mesh":
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
