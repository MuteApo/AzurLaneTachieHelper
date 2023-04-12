from .utility import create_window, decode_tex, encode_tex, get_rect_transform, parse_obj, read_img, save_img
from PIL import Image
from pyglet import app
import numpy as np
import os
import UnityPy


class TextureHelper():
    def __init__(self, chara, **kwargs):
        seq = chara.split('-')
        prefix = ''.join(seq[:len(seq)])
        self.chara = prefix[:-4] if prefix.endswith('_tex') else prefix
        self.enc_tex = self.chara + '-enc.png'
        self.dec_tex = self.chara + '-dec.png'
        self.mesh_obj = self.chara + '-mesh.obj'

    def _unpack(self):
        chara = self.chara + '_tex'
        assert os.path.exists(chara), f'{chara} not found'
        env = UnityPy.load(chara)

        tex2d = [_ for _ in env.objects if _.type.name == 'Texture2D'][0]
        tex2d.read().image.save(self.enc_tex)

        mesh = [_ for _ in env.objects if _.type.name == 'Mesh'][0]
        with open(self.mesh_obj, 'w', newline='') as f:
            f.write(mesh.read().export())

    def _parse(self):
        self.dec_size, self.mesh_data = parse_obj(self.mesh_obj)
        v, vt, f = self.mesh_data.values()

        print(f'[{str(self)}: INFO] Vertex count: {len(v)}')
        print(f'[{str(self)}: INFO] Texcoord count: {len(vt)}')
        print(f'[{str(self)}: INFO] Face count: {len(f)}')
        print(f'[{str(self)}: INFO] Mesh size: {self.dec_size}')


class DecodeHelper(TextureHelper):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._unpack()
        self._parse()

    def __str__(self):
        return 'DecodeHelper'

    def decode(self):
        enc_img = read_img(self.enc_tex)
        dec_img = decode_tex(enc_img, self.dec_size, *self.mesh_data.values())

        print(f'[{str(self)}: INFO] Texture size: {enc_img.shape[1::-1]} -> {self.dec_size}', )

        save_img(dec_img, self.dec_tex)


class EncodeHelper(TextureHelper):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not all([os.path.exists(self.enc_tex), os.path.exists(self.mesh_obj)]):
            self._unpack()
        self.enc_size = Image.open(self.enc_tex).size
        self._parse()

    def __str__(self):
        return 'EncodeHelper'

    def encode(self):
        dec_img = read_img(self.dec_tex)
        enc_img = encode_tex(dec_img, self.enc_size, *self.mesh_data.values())

        print(f'[{str(self)}: INFO] Texture size: {self.dec_size} -> {self.enc_size}', )

        save_img(enc_img, self.enc_tex)


class ViewHelper(TextureHelper):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._parse()

    def __str__(self):
        return 'ViewHelper'

    def display(self, **kwargs):
        enc_win, enc_batch, enc_draw = create_window(
            self.enc_tex,
            self.mesh_data['vt'],
            self.mesh_data['f'][:, :, 1],
            win_width=kwargs['win_width_enc'],
            **kwargs
        )

        @enc_win.event
        def on_draw():
            enc_win.clear()
            enc_batch.draw()

        dec_win, dec_batch, dec_draw = create_window(
            self.dec_tex,
            self.mesh_data['v'],
            self.mesh_data['f'][:, :, 0],
            win_width=kwargs['win_width_dec'],
            **kwargs
        )

        @dec_win.event
        def on_draw():
            dec_win.clear()
            dec_batch.draw()

        app.run()

        return enc_draw, dec_draw


class MergeHelper(TextureHelper):
    def __str__(self):
        return 'MergeHelper'

    def merge(self):
        _, _, x, y, w, h = get_rect_transform(self.chara[:-4])

        pf_dir = os.path.join(os.path.dirname(self.dec_tex), 'paintingface')
        if not os.path.exists(pf_dir + '-merge'):
            os.mkdir(pf_dir + '-merge')
        main = read_img(self.chara + '-dec.png')
        for _, _, files in os.walk(pf_dir):
            for img in files:
                print(os.path.join(pf_dir, img))
                diff = read_img(os.path.join(pf_dir, img))
                main[y:y + h, x:x + w] = diff[:, :]
                save_img(main, os.path.join(pf_dir + '-merge', img))


class SplitHelper(TextureHelper):
    def __str__(self):
        return 'SplitHelper'

    def split(self):
        _, face, x, y, w, h = get_rect_transform(self.chara)

        pf_dir = os.path.join(os.path.dirname(self.dec_tex), 'paintingface')
        if not os.path.exists(pf_dir + '-split'):
            os.mkdir(pf_dir + '-split')
        main = np.empty((*face['m_SizeDelta'].astype(np.int32)[::-1], 4), dtype=np.uint8)
        for _, _, files in os.walk(pf_dir + '-merge'):
            for img in files:
                print(os.path.join(pf_dir + '-merge', img))
                full = read_img(os.path.join(pf_dir + '-merge', img))
                main[:, :] = full[y:y + h, x:x + w]
                save_img(main, os.path.join(pf_dir + '-split', img))
