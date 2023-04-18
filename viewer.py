import argparse
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pyglet import app, gl, image, sprite, window

from src.module import TextureHelper
from src.utility import parse_obj, read_img, save_img, scale_img


class ViewHelper(TextureHelper):
    def __init__(self, label_size, label_color, bbox_color, **kwargs):
        super().__init__(**kwargs)
        self.font = ImageFont.truetype(os.path.join("font", "times.ttf"), label_size)
        self.label_color = label_color
        self.bbox_color = bbox_color

    def _mark(self, name, v, f):
        img = read_img(name)
        bbox = ImageDraw.ImageDraw(img)
        sub = Image.new("RGBA", img.size)
        label = ImageDraw.ImageDraw(sub)
        for id, rect in enumerate(zip(f[::2], f[1::2])):
            index = [*rect[0], *rect[1][1:]]
            coord = [v[_ - 1][:2] * img.size for _ in index]

            [bbox.line((*x, *y), self.bbox_color, 2) for x, y in zip(coord[:], coord[1:])]

            anchor = np.mean(coord[:-1], 0).astype(np.int32)
            x, y = anchor[0], img.size[1] - anchor[1]
            label.text((x, y), str(id + 1), self.label_color, self.font, "mm")

        img.alpha_composite(sub.transpose(Image.FLIP_TOP_BOTTOM))
        # save_img(img, name + "-mark")

        img = scale_img(img, 0.5)
        win = window.Window(img.width, img.height, name + ".png")
        gl.glClearColor(1, 1, 1, 1)

        tex2d = sprite.Sprite(
            image.ImageData(img.width, img.height, "RGBA", img.tobytes())
        )

        @win.event
        def on_draw():
            win.clear()
            tex2d.draw()

        return tex2d

    def display(self):
        name = self.chara.split("\\")[-1].split("_tex")[0]
        _, vt, f, v = parse_obj(self._mesh_obj(name)).values()

        enc_tex = self._mark(self._enc_tex(name), vt, f[:, :, 1])
        dec_tex = self._mark(self._dec_tex(name), v, f[:, :, 1])

        app.run()

        return enc_tex, dec_tex


parser = argparse.ArgumentParser(description="Azur Lane Tachie Viewer")
parser.add_argument("chara", type=str, help="tachie to view, eg. hailunna_h_rw")
parser.add_argument(
    "--label_size",
    metavar="S",
    type=int,
    default=28,
    help="size of labels in bounding box",
)
parser.add_argument(
    "--label_color",
    metavar="C",
    type=int,
    nargs=4,
    default=(238, 72, 102, 240),
    help="RGBA color of labels in bounding box",
)
parser.add_argument(
    "--bbox_color",
    metavar="C",
    type=int,
    nargs=4,
    default=(251, 218, 65, 240),
    help="RGBA color of bounding box",
)

if __name__ == "__main__":
    args = parser.parse_args().__dict__

    viewer = ViewHelper(**args)
    viewer.display()
