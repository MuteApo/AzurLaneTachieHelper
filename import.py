import os
import threading

import UnityPy
from PIL import Image
from UnityPy import Environment
from UnityPy.classes import Sprite, Texture2D
from UnityPy.enums import TextureFormat

from src.utility import check_dir

suffix = {
    "assets/artresource/atlas/loadingbg": "_hx",
    "assets/rescategories/jp/artresource/atlas/loadingbg": "_jp",
    "assets/rescategories/fanhx/artresource/atlas/loadingbg": "",
}


def exec(ab: str):
    env: Environment = UnityPy.load(os.path.join("loadingbg", ab))
    mod = False
    for k, v in env.container.items():
        sprite: Sprite = v.read()
        src = os.path.join("loadingbg_img", f"{sprite.name}{suffix[os.path.dirname(k)]}.png")
        if os.path.exists(src):
            img = Image.open(src)
            tex2d: Texture2D = sprite.m_RD.texture.read()
            tex2d.m_Width, tex2d.m_Height = img.size
            tex2d.set_image(img, target_format=TextureFormat.RGBA32)
            tex2d.save()
            mod = True

    if mod:
        path = os.path.join(outdir, ab)
        print(f"[INFO] Packing: {path}")
        with open(path, "wb") as f:
            f.write(env.file.save("lz4"))


outdir = "loadingbg_out"
check_dir(outdir)

tasks = [threading.Thread(target=exec, args=(_,)) for _ in os.listdir("loadingbg")]
[_.start() for _ in tasks]
[_.join() for _ in tasks]

os.system("pause")
