import argparse
import os
import threading
from pprint import pprint

import UnityPy
from PIL import Image
from UnityPy import Environment
from UnityPy.classes import TextAsset, Texture2D
from UnityPy.enums import ClassIDType, TextureFormat


def get_skel(env: Environment) -> dict[str, TextAsset]:
    skel: list[TextAsset] = [_.read() for _ in env.objects if _.type == ClassIDType.TextAsset]
    return {_.name.split(".")[0]: _ for _ in skel if _.name.endswith(".skel")}


def get_atlas(env: Environment) -> dict[str, TextAsset]:
    atlas: list[TextAsset] = [_.read() for _ in env.objects if _.type == ClassIDType.TextAsset]
    return {_.name.split(".")[0]: _ for _ in atlas if _.name.endswith(".atlas")}


def get_tex2d(env: Environment) -> dict[str, Texture2D]:
    tex2d: list[Texture2D] = [_.read() for _ in env.objects if _.type == ClassIDType.Texture2D]
    return {_.name: _ for _ in tex2d}


def get_parts(atlas: TextAsset) -> tuple[tuple[int, int], dict[str, dict]]:
    def parse(s: str):
        return tuple(eval(_) for _ in s.split(":")[-1].split(","))

    txt = atlas.text.splitlines()
    return parse(txt[2]), {
        txt[i]
        .strip()
        .lower(): {
            "rotate": eval(txt[i + 1].split()[-1].capitalize()),
            "xy": parse(txt[i + 2]),
            "size": parse(txt[i + 3]),
            "orig": parse(txt[i + 4]),
            "offset": parse(txt[i + 5]),
            "index": eval(txt[i + 6].split()[-1]),
        }
        for i in range(6, len(txt), 7)
    }


def get_rects(
    atlas: TextAsset, tex2d: Texture2D
) -> tuple[dict[str, Image.Image], tuple[int, int], dict[str, dict]]:
    shape, parts = get_parts(atlas)
    img = tex2d.image
    rects = {}
    for k, v in parts.items():
        rot, xy, size, orig, offset, idx = v.values()
        wh = size[::-1] if rot else size
        sub = img.crop((*xy, xy[0] + wh[0] - 1, xy[1] + wh[1] - 1))
        rects[k] = sub.rotate(-90, expand=True) if rot else sub
    return rects, shape, parts


def merge(*kv_list: dict):
    out = {}
    for x in kv_list[0].keys():
        out[x] = {kv[x] for kv in kv_list}
    return out


parser = argparse.ArgumentParser()
parser.add_argument("path", type=str, help="Path to the folder containing old & new spine")

if __name__ == "__main__":
    args = parser.parse_args()

    base = args.path.strip("\\/")
    print(f"[INFO] Base folder: {base}")
    name = os.path.basename(base)
    print(f"[INFO] Spine name: {name}")

    print("[INFO] Read old spine")
    old = UnityPy.load(os.path.join(base, "old", name + "_res"))
    old_skel = get_skel(old)
    old_atlas = get_atlas(old)
    old_tex2d = get_tex2d(old)
    pprint(merge(old_skel, old_atlas, old_tex2d))

    print("[INFO] Read new spine")
    new = UnityPy.load(os.path.join(base, "new", name + "_res"))
    new_skel = get_skel(new)
    new_atlas = get_atlas(new)
    new_tex2d = get_tex2d(new)
    pprint(merge(new_skel, new_atlas, new_tex2d))

    # relocate mode
    def recover1(
        name: str,
    ) -> Image.Image:
        old_rects, _, _ = get_rects(old_atlas[name], old_tex2d[name])
        new_rects, new_shape, new_parts = get_rects(new_atlas[name], new_tex2d[name])

        full = Image.new("RGBA", new_shape)
        for k, v in new_parts.items():
            rot, xy, size, orig, offset, idx = v.values()
            rect = old_rects[k] if k in old_rects else new_rects[k]
            sub = rect.rotate(90, expand=True) if rot else rect
            full.paste(sub, xy)

        print(f"[INFO] Reconstruct atlas for {name}")

        tex2d = new_tex2d[name]
        tex2d.m_Width, tex2d.m_Height = full.size
        tex2d.set_image(full, TextureFormat.RGBA32)
        tex2d.save()

    # replace mode
    def recover2(
        name: str,
    ) -> Image.Image:
        # skel_1 = old_skel[name]
        atlas_1 = old_atlas[name]
        tex2d_1 = old_tex2d[name]

        skel_2 = new_skel[name]
        atlas_2 = new_atlas[name]
        tex2d_2 = new_tex2d[name]

        path = os.path.join(base, f"{name}_s38.json")
        if not os.path.exists(path):
            path = os.path.join(base, f"{name}.json")
        if os.path.exists(path):
            print(f"[INFO] Found {path}")
            with open(path, "rb") as f:
                skel_2.script = f.read()
            skel_2.m_Name = f"{name}.json"
            skel_2.save()

            atlas_2.script = atlas_1.script
            atlas_2.save()

            tex2d_2.set_raw_data(tex2d_1.get_raw_data())

    mode = input("Recover Mode (1 for relocate, 2 for replace): ")
    assert mode in ["1", "2"], f"Unknow mode {mode}"

    tasks = [
        threading.Thread(target={"1": recover1, "2": recover2}[mode], args=(x,))
        for x in old_atlas.keys()
    ]
    [_.start() for _ in tasks]
    [_.join() for _ in tasks]

    out = os.path.join(base, "output")
    if not os.path.exists(out):
        os.mkdir(out)
    path = os.path.join(out, name + "_res")
    print(f"[INFO] Write into {path}")
    with open(path, "wb") as f:
        f.write(new.file.save("original"))

    os.system("pause")
