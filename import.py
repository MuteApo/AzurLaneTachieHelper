import os

import UnityPy
from PIL import Image
from UnityPy import Environment
from UnityPy.classes import Sprite, Texture2D
from UnityPy.enums import TextureFormat

from src.utility import check_dir

# for file in os.listdir("loadingbg_img"):
#     name, ext = file.split(".")
#     os.system(f"cd loadingbg_img && rename {file} {name[:-1]}.{ext}")

outdir = "loadingbg_out"
check_dir(outdir)
for file in os.listdir("loadingbg"):
    env: Environment = UnityPy.load(os.path.join("loadingbg", file))
    mod = False
    for k, v in env.container.items():
        sprite: Sprite = v.read()
        tex2d: Texture2D = sprite.m_RD.texture.read()
        name = sprite.name
        img: Image.Image = sprite.image
        src = os.path.join("loadingbg_img", f"{name}.png")
        if os.path.exists(src):
            img = Image.open(src)
            tex2d.set_image(img, target_format=TextureFormat.RGBA32, in_cab=True)
            mod = True
        tex2d.save()
    if mod:
        print(f"[INFO] Packing: {os.path.join(outdir, file)}")
        with open(os.path.join(outdir, file), "wb") as f:
            f.write(env.file.save("lz4"))
