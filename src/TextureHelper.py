import os

import numpy as np
import UnityPy
from PIL import Image
from UnityPy.classes import GameObject, Mesh, MonoBehaviour, RectTransform, Texture2D
from UnityPy.enums import TextureFormat

from .utility import check_dir, convert, get_rt_name, filter_typename, parse_obj


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

    def _extract(self, name: str, path: str):
        env = UnityPy.load(path)

        # extract mesh
        mesh: list[Mesh] = filter_typename(env, "Mesh")
        if len(mesh) == 0:
            env = UnityPy.load(path.split("_tex")[0] + "_n_tex")
            mesh: list[Mesh] = filter_typename(env, "Mesh")
        self.mesh_obj[name] = parse_obj(mesh[0].export().split("\r\n")[:-1])

        # extract texture2d
        tex2d: list[Texture2D] = filter_typename(env, "Texture2D")
        self.enc_img[name] = tex2d[0].image.transpose(Image.FLIP_TOP_BOTTOM)

        self.whs[name] = (tex2d[0].m_Width, tex2d[0].m_Height)

    def _replace(self, folder, asset, img_dict):
        asset_path = os.path.join(self.dir, folder, asset)
        assert os.path.exists(asset_path), f"file {asset_path} not found"

        env = UnityPy.load(asset_path)
        for _ in env.objects:
            if _.type.name == "Texture2D":
                tex2d: Texture2D = _.read()
                tex2d.set_image(
                    img_dict[tex2d.name].transpose(Image.FLIP_TOP_BOTTOM),
                    target_format=TextureFormat.RGBA32,
                    in_cab=True,
                )
                tex2d.save()

        check_dir(self.dir, "output", folder)
        with open(os.path.join(self.dir, "output", folder, asset), "wb") as f:
            f.write(env.file.save("lz4"))

    def _parse_rect(self, rt: RectTransform, mbs: list[MonoBehaviour]):
        go: GameObject = rt.m_GameObject.read()
        mb = [_.read() for _ in mbs if _.m_GameObject.path_id == go.path_id][0]
        rss = np.array([*mb.mRawSpriteSize.values()], dtype=np.int32)

        return tuple(rss), get_rt_name(rt), convert(rt)
