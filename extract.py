import os
import threading

import UnityPy
from UnityPy import Environment
from UnityPy.classes import Sprite

from src.utility import check_dir

suffix = {
    "assets/artresource/atlas/loadingbg": "_hx",
    "assets/rescategories/jp/artresource/atlas/loadingbg": "_jp",
    "assets/rescategories/fanhx/artresource/atlas/loadingbg": "",
}


def exec(ab: str):
    env: Environment = UnityPy.load(os.path.join("loadingbg", ab))
    for k, v in env.container.items():
        sprite: Sprite = v.read()
        dst = os.path.join(outdir, f"{sprite.name}{suffix[os.path.dirname(k)]}.png")
        print("[INFO] Dumping:", dst)
        sprite.image.save(dst)


outdir = "loadingbg_img"
check_dir(outdir)

tasks = [threading.Thread(target=exec, args=(_,)) for _ in os.listdir("loadingbg")]
[_.start() for _ in tasks]
[_.join() for _ in tasks]

os.system("pause")
