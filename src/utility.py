from PIL import Image
from pyglet import gl, graphics, image, shapes, sprite, text, window
import numpy as np
import pprint
import UnityPy


def parse_obj(mesh):  
    with open(mesh) as file:
        lines = [_.replace('\n', '').split(' ') for _ in file.readlines()]

        data = {
            'g': [],   # group name
            'v': [],   # geometric vertices
            'vt': [],  # texture vertices
            'f': []    # face, indexed as v/vt/vn
        }
        for line in lines:
            data[line[0]].append(line[1:])

        v = np.array(data['v'], dtype=np.float32)
        vt = np.array(data['vt'], dtype=np.float32)
        f = np.array(
            [[[___ for ___ in __.split('/')] for __ in _] for _ in data['f']],
            dtype=np.int32
        )

        v[:, 0] = -v[:, 0]
        s = np.stack(v, -1).max(-1) + 1

    return tuple(s.astype(np.int32)[:2]), {'v': v / s, 'vt': vt, 'f': f}


def read_img(filename):
    return np.array(Image.open(filename).transpose(Image.FLIP_TOP_BOTTOM))


def save_img(data, filename):
    Image.fromarray(data).transpose(Image.FLIP_TOP_BOTTOM).save(filename)


def get_img_area(data, scaler):
    coord = np.round(data * scaler).astype(np.int32)
    x, y = np.stack(coord, -1).min(-1)
    w, h = np.stack(coord, -1).max(-1) - [x, y]
    return x, y, w, h


def decode_tex(enc_img, dec_size, v, vt, f):
    dec_img = np.empty((*dec_size[::-1], 4), dtype=np.uint8)
    enc_size = enc_img.shape[1::-1]

    for rect in zip(f[::2], f[1::2]):
        index_v, index_vt = np.stack([*rect[0][:2, :2], *rect[1][:2, :2]], -1)

        x1, y1, _, _ = get_img_area(v[index_v - 1, :2], dec_size)
        x2, y2, w, h = get_img_area(vt[index_vt - 1], enc_size)

        dec_img[y1:y1 + h, x1:x1 + w, :] = enc_img[y2:y2 + h, x2:x2 + w, :]

    return dec_img


def encode_tex(dec_img, enc_size, v, vt, f):
    enc_img = np.empty((*enc_size[::-1], 4), dtype=np.uint8)
    dec_size = dec_img.shape[1::-1]

    for rect in zip(f[::2], f[1::2]):
        index_v, index_vt = np.stack([*rect[0][:2, :2], *rect[1][:2, :2]], -1)

        x1, y1, _, _ = get_img_area(v[index_v - 1, :2], dec_size)
        x2, y2, w, h = get_img_area(vt[index_vt - 1], enc_size)

        enc_img[y2:y2 + h, x2:x2 + w, :] = dec_img[y1:y1 + h, x1:x1 + w, :]

    return enc_img


def create_window(
    tex, v, f, win_width, padding, label_size, label_color, bbox_color, **kwargs
):
    img = image.load(tex)
    img_size = np.array([win_width, win_width / img.width * img.height])
    win_size = np.round(img_size + padding * 2).astype(np.int32)
    win = window.Window(*win_size, tex)
    gl.glClearColor(1, 1, 1, 0)
    batch = graphics.Batch()
    line_list = []
    label_list = []

    tex2d = sprite.Sprite(img, padding, padding, batch=batch)
    tex2d.scale_x, tex2d.scale_y = img_size / [img.width, img.height]

    for id, rect in enumerate(zip(f[::2], f[1::2])):
        index = np.reshape([list(zip(_, _[1:])) for _ in rect], (4, -1))
        # print(index)
        coord = np.reshape(
            [[v[__ - 1][:2] * img_size + padding for __ in _] for _ in index], (4, -1)
        )
        # print(coord)
        label_list += [
            text.Label(
                str(id + 1),
                font_name='Times New Roman',
                font_size=label_size,
                color=label_color,
                x=np.round((coord[0][0] + coord[0][2]) / 2),
                y=np.round((coord[1][1] + coord[1][3]) / 2),
                anchor_x='center',
                anchor_y='center',
                batch=batch
            )
        ]
        line_list += [shapes.Line(*_, color=bbox_color, batch=batch) for _ in coord]

    return win, batch, (tex2d, line_list, label_list)


def get_rect_transform(filename):
    assets = UnityPy.load(filename)
    game_objects = [_.read() for _ in assets.objects if _.type.name == 'GameObject']
    face_gameobj = [_ for _ in game_objects if _.m_Name == 'face'][0]
    face_rect = face_gameobj.read().m_Component[0].component.read()
    base_rect = face_rect.read().m_Father.read()

    print('[INFO] Face GameObject PathID:', face_gameobj.path_id)
    print('[INFO] Face RectTransform PathID:', face_rect.path_id)
    print('[INFO] Base RectTransform PathID:', base_rect.path_id)

    def convert(raw: dict) -> dict[str, np.ndarray]:
        entry = ['m_AnchorMin', 'm_AnchorMax', 'm_AnchoredPosition', 'm_SizeDelta']
        return {_: np.array([*raw[_].values()]) for _ in entry}

    base = convert(base_rect.to_dict())
    face = convert(face_rect.to_dict())

    print('[INFO] Face RectTransform data:')
    pprint.pprint(base)
    print('[INFO] Base RectTransform data:')
    pprint.pprint(face)

    face['m_AnchorCenter'] = np.mean([face['m_AnchorMax'], face['m_AnchorMin']])

    anchor = face['m_AnchorCenter'] * base['m_SizeDelta']
    pivot = anchor + face['m_AnchoredPosition']
    align = pivot - face['m_AnchorCenter'] * face['m_SizeDelta']
    x, y = np.round(align).astype(np.int32)
    w, h = face['m_SizeDelta'].astype(np.int32)

    print('[INFO] Paintingface area:', x, y, w, h)

    return base, face, x, y, w, h
