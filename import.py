import os
import threading

import UnityPy
from PIL import Image
from UnityPy import Environment
from UnityPy.classes import Sprite, Texture2D
from UnityPy.enums import ClassIDType, TextureFormat

from src.utility import check_dir

suffix = {
    "assets/artresource/atlas/loadingbg": "_hx",
    "assets/rescategories/jp/artresource/atlas/loadingbg": "_jp",
    "assets/rescategories/fanhx/artresource/atlas/loadingbg": "",
}
exts = ["png", "jpg", "jpeg"]


def exec(ab: str):
    env: Environment = UnityPy.load(os.path.join("loadingbg", ab))
    mod = False
    for k, v in env.container.items():
        if v.type == ClassIDType.Sprite:
            sprite: Sprite = v.read()
            tex2d: Texture2D = sprite.m_RD.texture.read()
        elif v.type == ClassIDType.Texture2D:
            tex2d: Texture2D = v.read()
        else:
            raise ValueError(v.type)
        file = tex2d.name + suffix[os.path.dirname(k)]

        for x in exts:
            src = os.path.join("loadingbg_img", f"{file}.{x}")
            if os.path.exists(src):
                print(f"[INFO] Processing: {src}")
                img = Image.open(src)
                if sprite is not None:
                    sprite.m_Rect.width, sprite.m_Rect.height = img.size
                    sprite.m_RD.textureRect.width, sprite.m_RD.textureRect.height = img.size
                    sprite.save()
                tex2d.m_Width, tex2d.m_Height = img.size
                tex2d.set_image(img, target_format=TextureFormat.RGBA32)
                tex2d.save()
                mod = True
                break

    if mod:
        path = os.path.join(outdir, ab)
        with open(path, "wb") as f:
            f.write(env.file.save("lz4"))


outdir = "loadingbg_out"
check_dir(outdir)

tasks = [threading.Thread(target=exec, args=(_,)) for _ in os.listdir("loadingbg")]
[_.start() for _ in tasks]
[_.join() for _ in tasks]

os.system("pause")
