import os
import threading

import UnityPy
from UnityPy import Environment
from UnityPy.classes import Sprite, Texture2D
from UnityPy.enums import ClassIDType

from src.utility import check_dir

suffix = {
    "assets/artresource/atlas/loadingbg": "_hx",
    "assets/rescategories/jp/artresource/atlas/loadingbg": "_jp",
    "assets/rescategories/fanhx/artresource/atlas/loadingbg": "",
}


def exec(ab: str):
    env: Environment = UnityPy.load(os.path.join("loadingbg", ab))
    for k, v in env.container.items():
        if v.type == ClassIDType.Sprite:
            sprite: Sprite = v.read()
            tex2d: Texture2D = sprite.m_RD.texture.read()
        elif v.type == ClassIDType.Texture2D:
            tex2d: Texture2D = v.read()
        else:
            raise ValueError(v.type)
        file = tex2d.name + suffix[os.path.dirname(k)]

        dst = os.path.join(outdir, f"{file}.png")
        print("[INFO] Dumping:", dst)
        tex2d.image.save(dst)


outdir = "loadingbg_img"
check_dir(outdir)

tasks = [threading.Thread(target=exec, args=(_,)) for _ in os.listdir("loadingbg")]
[_.start() for _ in tasks]
[_.join() for _ in tasks]

os.system("pause")
