from .utility import create_window, decode_tex, encode_tex, parse_obj, read_img, save_img
from pyglet import app


class TextureHelper():
    def __init__(self, chara, logging=False, **kwargs):
        self.enc_tex = chara + '-enc.png'
        self.dec_tex = chara + '-dec.png'
        self.mesh = chara + '-mesh.obj'
        self.logging = logging

    def parse(self):
        self.dec_size, self.mesh_data = parse_obj(self.mesh)
        v, vt, f = self.mesh_data.values()

        if self.logging:
            print(f'[{str(self)}: INFO] Collecting wavefront metadata...')
            print(f'[{str(self)}: INFO] Vertex count:{len(v)}')
            print(f'[{str(self)}: INFO] Texcoord count:{len(vt)}')
            print(f'[{str(self)}: INFO] Face count:{len(f)}')
            print(f'[{str(self)}: INFO] Mesh size:{self.dec_size}')


class DecodeHelper(TextureHelper):
    def __str__(self):
        return 'DecodeHelper'

    def decode(self):
        if not hasattr(self, 'data'):
            self.parse()

        enc_img = read_img(self.enc_tex)
        dec_img = decode_tex(enc_img, self.dec_size, *self.mesh_data.values())

        if self.logging:
            print(f'[{str(self)}: INFO] Processing texture...')
            print(f'[{str(self)}: INFO] Source image size:', enc_img.shape[1::-1])
            print(f'[{str(self)}: INFO] Target image size:', self.dec_size)
            print(f'[{str(self)}: INFO] Dumping image to file...')

        save_img(dec_img, self.dec_tex)


class EncodeHelper(TextureHelper):
    def __str__(self):
        return 'EncodeHelper'

    def encode(self, enc_size, **kwargs):
        if not hasattr(self, 'data'):
            self.parse()

        dec_img = read_img(self.dec_tex)
        enc_img = encode_tex(dec_img, enc_size, *self.mesh_data.values())

        if self.logging:
            print(f'[{str(self)}: INFO] Processing texture...')
            print(f'[{str(self)}: INFO] Source image size:', self.dec_size)
            print(f'[{str(self)}: INFO] Target image size:', enc_size)
            print(f'[{str(self)}: INFO] Dumping image to file...')

        save_img(enc_img, self.enc_tex)


class ViewHelper(TextureHelper):
    def __str__(self):
        return 'ViewHelper'

    def display(self, **kwargs):
        if not hasattr(self, 'data'):
            self.parse()

        enc_draw = create_window(
            self.enc_tex,
            self.mesh_data['vt'],
            self.mesh_data['f'][:, :, 1],
            win_width=kwargs['win_width_enc'],
            **kwargs
        )

        dec_draw = create_window(
            self.dec_tex,
            self.mesh_data['v'],
            self.mesh_data['f'][:, :, 0],
            win_width=kwargs['win_width_dec'],
            **kwargs
        )

        app.run()

        return enc_draw, dec_draw
