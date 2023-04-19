import argparse
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageTk

from src.module import TextureHelper
from src.utility import parse_obj, read_img, save_img, scale_img
import tkinter as tk


class ViewHelper(TextureHelper):
    def __init__(self, chara, label_size, label_color, bbox_color, **kwargs):
        super().__init__(chara, **kwargs)
        self.font = ImageFont.truetype(os.path.join("font", "times.ttf"), label_size)
        self.label_color = label_color
        self.bbox_color = bbox_color

    def display(self):
        name = self.chara.split("\\")[-1].split("_tex")[0]
        _, vt, f, v = parse_obj(self._mesh_obj(name)).values()

        main = tk.Tk()
        main.withdraw()
        img_list = []

        def _mark(name, v, f):
            img = read_img(name)
            bbox = ImageDraw.ImageDraw(img)
            sub = Image.new("RGBA", img.size, (255, 255, 255, 0))
            label = ImageDraw.ImageDraw(sub)
            for id, rect in enumerate(zip(f[::2], f[1::2])):
                index = [*rect[0], *rect[1][1:]]
                pos = [v[_ - 1][:2] * img.size for _ in index]

                [bbox.line((*x, *y), self.bbox_color, 2) for x, y in zip(pos[:], pos[1:])]

                anchor = np.mean(pos[:-1], 0).astype(np.int32)
                x, y = anchor[0], img.size[1] - anchor[1]
                label.text((x, y), str(id + 1), self.label_color, self.font, "mm")

            img.alpha_composite(sub.transpose(Image.FLIP_TOP_BOTTOM))
            # save_img(img, name + "-mark")

            img = scale_img(img, 0.5).transpose(Image.FLIP_TOP_BOTTOM)
            img_tk = ImageTk.PhotoImage(img)
            img_list.append(img_tk)

            win = tk.Toplevel(main, takefocus=True)
            win.geometry("%dx%d" % img.size)
            win.title(name + ".png")
            win.protocol("WM_DELETE_WINDOW", lambda: main.quit())
            draw = tk.Label(win, image=img_tk)
            draw.pack()

        _mark(self._enc_tex(name), vt, f[:, :, 1])
        _mark(self._dec_tex(name), v, f[:, :, 1])

        main.mainloop()


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
