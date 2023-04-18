import os

import numpy as np
import UnityPy
from PIL import Image
from UnityPy.classes import GameObject, Mesh, MonoBehaviour, RectTransform, Texture2D
from UnityPy.enums import TextureFormat

from .utility import check_dir, convert, get_rt_name


class TextureHelper:
    def __init__(self, chara, **kwargs):
        self.chara = "".join([chara.split("-")[0], *chara.split("-")[1:-1]])
        self.dir = os.path.dirname(chara)

    def _enc_tex(self, filename):
        return os.path.join(self.dir, filename + "-enc")

    def _dec_tex(self, filename):
        return os.path.join(self.dir, filename + "-dec")

    def _mesh_obj(self, filename):
        return os.path.join(self.dir, filename + "-mesh")

    def _asset_name(self, asset):
        return asset.split("/")[-1].split("\\")[-1].split("_tex")[0]

    def _extract(self, asset, mesh_only=False):
        asset_path = os.path.join(self.dir, asset)
        assert os.path.exists(asset_path), f"file {asset_path} not found"

        env = UnityPy.load(asset_path)

        print("[INFO] Asset bundle:", asset_path)

        # extract mesh
        mesh: list[Mesh] = [_.read() for _ in env.objects if _.type.name == "Mesh"]
        if len(mesh) == 0:
            env = UnityPy.load(
                os.path.join(
                    os.path.dirname(asset_path), self._asset_name(self.chara) + "_n_tex"
                )
            )
        mesh: list[Mesh] = [_.read() for _ in env.objects if _.type.name == "Mesh"]
        with open(self._mesh_obj(self._asset_name(asset)), "w", newline="") as f:
            f.write(mesh[0].export())

        # extract texture2d
        tex2d: list[Texture2D] = [
            _.read() for _ in env.objects if _.type.name == "Texture2D"
        ]
        if not mesh_only:
            tex2d[0].image.save(self._enc_tex(self._asset_name(asset)) + ".png", "png")

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
