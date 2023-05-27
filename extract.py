import os

import UnityPy
from PIL import Image
from UnityPy import Environment
from UnityPy.classes import Sprite

from src.utility import check_dir

outdir = "loadingbg_img"
check_dir(outdir)
for file in os.listdir("loadingbg"):
    env: Environment = UnityPy.load(os.path.join("loadingbg", file))
    for k, v in env.container.items():
        sprite: Sprite = v.read()
        name = sprite.name
        img: Image.Image = sprite.image
        if k.startswith("assets/artresource/atlas/loadingbg/"):
            target = os.path.join(outdir, f"{name}_hx.png")
        elif k.startswith("assets/rescategories/fanhx/artresource/atlas/loadingbg/"):
            target = os.path.join(outdir, f"{name}.png")
        else:
            raise ValueError(k)
        print("[INFO] Dumping:", target)
        img.save(target)
