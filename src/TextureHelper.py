import os

import numpy as np
import UnityPy
from PIL import Image
from UnityPy.classes import GameObject, Mesh, MonoBehaviour, RectTransform, Texture2D
from UnityPy.enums import TextureFormat

from .utility import check_dir, convert, get_rt_name


class TextureHelper:
    def __init__(self, path):
        self.path = path
        self.dir = os.path.dirname(path)
        self.file = os.path.basename(path)

    def _enc_img(self, file: str) -> str:
        return file + "-enc"

    def _dec_img(self, file: str) -> str:
        return file + "-dec"

    def _mesh_obj(self, file: str) -> str:
        return file + "-mesh"

    def _asset_name(self, file: str) -> str:
        return file.split("_tex")[0]

    def _extract(self, asset_path, output_dir, mesh_only=False):
        env = UnityPy.load(asset_path)

        print("[INFO] Asset bundle:", asset_path)

        output_name = os.path.join(
            output_dir, os.path.basename(self._asset_name(asset_path))
        )

        # extract mesh
        mesh: list[Mesh] = [_.read() for _ in env.objects if _.type.name == "Mesh"]
        if len(mesh) == 0:
            env = UnityPy.load(self._asset_name(asset_path) + "_n_tex")
        mesh: list[Mesh] = [_.read() for _ in env.objects if _.type.name == "Mesh"]
        with open(self._mesh_obj(output_name) + ".obj", "w", newline="") as f:
            f.write(mesh[0].export())

        # extract texture2d
        tex2d: list[Texture2D] = [
            _.read() for _ in env.objects if _.type.name == "Texture2D"
        ]
        if not mesh_only:
            tex2d[0].image.save(self._enc_img(output_name) + ".png", "png")

        return tex2d[0].m_Width, tex2d[0].m_Height

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
