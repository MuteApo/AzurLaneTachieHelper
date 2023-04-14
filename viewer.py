from src.module import TextureHelper
from src.utility import parse_obj
from pyglet import app, gl, graphics, image, shapes, sprite, text, window
import numpy as np
import argparse


class ViewHelper(TextureHelper):
    def __init__(
        self,
        win_width_enc,
        win_width_dec,
        padding,
        label_size,
        label_color,
        bbox_color,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.win_width_enc = win_width_enc
        self.win_width_dec = win_width_dec
        self.padding = padding
        self.label_size = label_size
        self.label_color = label_color
        self.bbox_color = bbox_color

    def _create_window(self, tex, v, f, win_width):
        img = image.load(tex)
        img_size = np.array([win_width, win_width / img.width * img.height])
        win_size = np.round(img_size + self.padding * 2).astype(np.int32)
        win = window.Window(*win_size, tex)
        gl.glClearColor(1, 1, 1, 0)
        batch = graphics.Batch()
        line_list = []
        label_list = []

        tex2d = sprite.Sprite(img, self.padding, self.padding, batch=batch)
        tex2d.scale_x, tex2d.scale_y = img_size / [img.width, img.height]

        for id, rect in enumerate(zip(f[::2], f[1::2])):
            index = np.reshape([list(zip(_, _[1:])) for _ in rect], (4, -1))
            # print(index)
            coord = np.reshape(
                [[v[__ - 1][:2] * img_size + self.padding for __ in _] for _ in index], (4, -1)
            )
            # print(coord)
            label_list += [
                text.Label(
                    str(id + 1),
                    font_name='Times New Roman',
                    font_size=self.label_size,
                    color=self.label_color,
                    x=np.round((coord[0][0] + coord[0][2]) / 2),
                    y=np.round((coord[1][1] + coord[1][3]) / 2),
                    anchor_x='center',
                    anchor_y='center',
                    batch=batch
                )
            ]
            line_list += [shapes.Line(*_, color=self.bbox_color, batch=batch) for _ in coord]

        return win, batch, (tex2d, line_list, label_list)

    def display(self, **kwargs):
        name = self.chara.split('\\')[-1].split('_tex')[0]
        mesh_data = parse_obj(self._mesh_obj(name))

        enc_win, enc_batch, enc_draw = self._create_window(
            self._enc_tex(name),
            mesh_data['vt'],
            mesh_data['f'][:, :, 1],
            self.win_width_enc,
            **kwargs
        )

        @enc_win.event
        def on_draw():
            enc_win.clear()
            enc_batch.draw()

        dec_win, dec_batch, dec_draw = self._create_window(
            self._dec_tex(name),
            mesh_data['v_normalized'],
            mesh_data['f'][:, :, 0],
            self.win_width_dec,
            **kwargs
        )

        @dec_win.event
        def on_draw():
            dec_win.clear()
            dec_batch.draw()

        app.run()

        return enc_draw, dec_draw


parser = argparse.ArgumentParser(description='Azur Lane Tachie Viewer')
parser.add_argument('chara', type=str, help='tachie to view, eg. hailunna_h_rw')
parser.add_argument(
    '--win_width_enc', metavar='W', type=int,
    default=1440, help='display width of encoded image'
)
parser.add_argument(
    '--win_width_dec', metavar='W', type=int,
    default=1080, help='display width of decoded image'
)
parser.add_argument(
    '-p', '--padding', metavar='P', type=int, default=10, help='padding for image in window'
)
parser.add_argument(
    '--label_size', metavar='S', type=int, default=12, help='size of labels in bouding box'
)
parser.add_argument(
    '--label_color', metavar='C', type=int, nargs=4,
    default=[157, 41, 50, 196], help='RGBA color of labels in bouding box'
)
parser.add_argument(
    '--bbox_color', metavar='C', type=int, nargs=4,
    default=[217, 182, 18, 196], help='RGBA color of bouding box'
)

if __name__ == '__main__':
    args = parser.parse_args().__dict__

    viewer = ViewHelper(**args)
    viewer.display()
