from .utility import *
from PIL import Image
from pyglet import app
import numpy as np
import os
import UnityPy
from UnityPy.classes import GameObject, RectTransform, AssetBundle, MonoBehaviour, Texture2D, Mesh
from typing import List, Dict
from pprint import pprint


class TextureHelper():
    def __init__(self, chara, **kwargs):
        self.chara = chara
        self.dir = os.path.dirname(chara)

    def _enc_tex(self, filename):
        return os.path.join(self.dir, filename + '-enc.png')

    def _dec_tex(self, filename):
        return os.path.join(self.dir, filename + '-dec.png')

    def _mesh_obj(self, filename):
        return os.path.join(self.dir, filename + '-mesh.obj')

    def _asset_name(self, asset):
        return asset.split('/')[-1].split('\\')[-1].split('_tex')[0]

    def _extract(self, asset, mesh_only=False):
        asset_path = os.path.join(self.dir, asset)
        assert os.path.exists(asset_path), f'file {asset_path} not found'

        env = UnityPy.load(asset_path)

        print('[INFO] Asset bundle:', asset_path)

        # extract texture2d
        tex2d: Texture2D = [_.read() for _ in env.objects if _.type.name == 'Texture2D'][0]
        if not mesh_only:
            tex2d.image.save(self._enc_tex(self._asset_name(asset)))

        # extract mesh
        mesh: Mesh = [_.read() for _ in env.objects if _.type.name == 'Mesh'][0]
        with open(self._mesh_obj(self._asset_name(asset)), 'w', newline='') as f:
            f.write(mesh.export())

        return np.array([tex2d.m_Width, tex2d.m_Height])


class DecodeHelper(TextureHelper):
    def decode(self):
        env = UnityPy.load(self.chara)

        # resolve assetbundle dependencies
        asset_bundle: AssetBundle = [_.read() for _ in env.objects if _.type.name == 'AssetBundle'][0]
        [self._extract(_) for _ in asset_bundle.m_Dependencies]

        gos: List[GameObject] = [_.read() for _ in env.objects if _.type.name == 'GameObject']
        mbs: List[MonoBehaviour] = [_.read() for _ in env.objects if _.type.name == 'MonoBehaviour']
        base_go: GameObject = [_.read() for _ in env.container.values()][0]
        base_rt: RectTransform = base_go.m_Transform.read()
        base_mb: MonoBehaviour = [_.read() for _ in mbs if _.m_GameObject.path_id == base_go.path_id][0]
        base_rss = np.array([*base_mb.mRawSpriteSize.values()], dtype=np.int32)
        base_info = convert(base_rt)
        base_pivot = base_info['m_SizeDelta'] * base_info['m_Pivot']

        print('[INFO] RectTransform:', base_rt, base_go.name)
        pprint(base_info)
        # print(base_pivot)

        mesh_data = parse_obj(self._mesh_obj(base_go.name))
        enc_img = read_img(self._enc_tex(base_go.name))
        dec_img = decode_tex(enc_img, base_rss, *mesh_data.values())
        # save_img(dec_img, os.path.join(self.dir, base_go.name + '-tmp.png'))

        shape = np.array([*base_rt.m_SizeDelta.values()], dtype=np.int32)
        full = Image.fromarray(dec_img).resize(tuple(shape), Image.Resampling.LANCZOS)
        save_img(np.array(full), self._dec_tex(base_go.name))

        if 'layers' in [_.name for _ in gos]:
            base_children: List[RectTransform] = [_.read() for _ in base_rt.m_Children]
            layers_rect: RectTransform = [_ for _ in base_children if get_rect_name(_) == 'layers'][0]
            layers_children: List[RectTransform] = [_.read() for _ in layers_rect.m_Children]
            layers_info = convert(layers_rect)
            layers_pivot = base_pivot + layers_info['m_LocalPosition'][:2]

            print('[INFO]', layers_rect, get_rect_name(layers_rect))
            pprint(layers_info)

            for child_rect in layers_children:
                child_go: GameObject = child_rect.m_GameObject.read()
                child_mb: MonoBehaviour = [_.read() for _ in mbs if _.m_GameObject.path_id == child_go.path_id][0]
                child_rss = np.array([*child_mb.mRawSpriteSize.values()], dtype=np.int32)
                child_name = get_rect_name(child_rect)
                child_info = convert(child_rect)
                child_pivot = layers_pivot + child_info['m_LocalPosition'][:2]

                print('[INFO]', child_rect, child_name)
                pprint(child_info)

                mesh_data = parse_obj(self._mesh_obj(child_name))
                enc_img = read_img(self._enc_tex(child_name))
                dec_img = decode_tex(enc_img, child_rss, *mesh_data.values())
                # save_img(dec_img, os.path.join(self.dir, child_name + '-tmp.png'))

                child_offset = child_pivot - child_info['m_Pivot'] * child_info['m_SizeDelta']
                x, y = np.maximum(np.round(child_offset), 0).astype(np.int32)
                w, h = np.minimum(child_info['m_SizeDelta'] + [x, y], shape).astype(np.int32) - [x, y]
                # print(x, y, w, h)

                sub = np.empty((*shape[::-1], 4), dtype=np.uint8)
                sub[y:y + h, x:x + w] = resize_img(dec_img, (w, h))[:, :]
                save_img(sub, self._dec_tex(child_name))

                full.alpha_composite(Image.fromarray(sub))

        save_img(np.array(full), os.path.join(self.dir, base_go.name + '-full.png'))


class EncodeHelper(TextureHelper):
    def encode(self):
        env = UnityPy.load(self.chara)

        # resolve assetbundle dependencies
        abs: List[AssetBundle] = [_.read() for _ in env.objects if _.type.name == 'AssetBundle']
        enc_whs = {
            self._asset_name(_): self._extract(_, mesh_only=True) for _ in abs[0].m_Dependencies
        }

        gos: List[GameObject] = [_.read() for _ in env.objects if _.type.name == 'GameObject']
        mbs: List[MonoBehaviour] = [_.read() for _ in env.objects if _.type.name == 'MonoBehaviour']
        base_go: GameObject = [_.read() for _ in env.container.values()][0]
        base_rt: RectTransform = base_go.m_Transform.read()
        base_mb: MonoBehaviour = [_.read() for _ in mbs if _.m_GameObject.path_id == base_go.path_id][0]
        base_rss = np.array([*base_mb.mRawSpriteSize.values()], dtype=np.int32)
        base_info = convert(base_rt)
        base_pivot = base_info['m_SizeDelta'] * base_info['m_Pivot']

        print('[INFO]', base_rt, base_go.name)
        pprint(base_info)

        mesh_data = parse_obj(self._mesh_obj(base_go.name))
        dec_img = read_img(self._dec_tex(base_go.name))
        # save_img(dec_img, os.path.join(self.dir, base_go.name + '-tmp.png'))

        enc_img = encode_tex(dec_img, enc_whs[base_go.name], *mesh_data.values())
        save_img(enc_img, self._enc_tex(base_go.name))

        if 'layers' in [_.name for _ in gos]:
            base_children: List[RectTransform] = [_.read() for _ in base_rt.m_Children]
            layers_rt: RectTransform = [_ for _ in base_children if get_rect_name(_) == 'layers'][0]
            layers_children: List[RectTransform] = [_.read() for _ in layers_rt.m_Children]
            layers_info = convert(layers_rt)
            layers_pivot = base_pivot + layers_info['m_LocalPosition'][:2]

            print('[INFO]', layers_rt, get_rect_name(layers_rt))
            pprint(layers_info)

            for child_rect in layers_children:
                child_go: GameObject = child_rect.m_GameObject.read()
                child_mb: MonoBehaviour = [_.read() for _ in mbs if _.m_GameObject.path_id == child_go.path_id][0]
                child_rss = np.array([*child_mb.mRawSpriteSize.values()], dtype=np.int32)
                child_name = get_rect_name(child_rect)
                child_info = convert(child_rect)
                child_pivot = layers_pivot + child_info['m_LocalPosition'][:2]

                print('[INFO]', child_rect, child_name)
                pprint(child_info)

                child_offset = child_pivot - child_info['m_SizeDelta'] * child_info['m_Pivot']
                x, y = np.round(child_offset).astype(np.int32)
                w, h = child_rss
                # print(x, y, w, h)

                mesh_data = parse_obj(self._mesh_obj(child_name))
                dec_img = read_img(self._dec_tex(child_name))[y:y + h, x:x + w]
                # save_img(dec_img, self.dir, child_name + '-tmp.png'))

                enc_img = encode_tex(dec_img, enc_whs[child_name], *mesh_data.values())
                save_img(enc_img, self._enc_tex(child_name))


class ViewHelper(TextureHelper):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def display(self, **kwargs):
        name = self.chara.split('\\')[-1].split('_tex')[0]
        mesh_data = parse_obj(self._mesh_obj(name))

        enc_win, enc_batch, enc_draw = create_window(
            self._enc_tex(name),
            mesh_data['vt'],
            mesh_data['f'][:, :, 1],
            win_width=kwargs['win_width_enc'],
            **kwargs
        )

        @enc_win.event
        def on_draw():
            enc_win.clear()
            enc_batch.draw()

        dec_win, dec_batch, dec_draw = create_window(
            self._dec_tex(name),
            mesh_data['v_normalized'],
            mesh_data['f'][:, :, 0],
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
    def merge(self):
        base, _, x, y, w, h = get_rect_transform(os.path.join(self.dir, self._asset_name(self.chara)))

        pf_dir = os.path.join(self.dir, 'paintingface')
        if not os.path.exists(pf_dir + '-merge'):
            os.mkdir(pf_dir + '-merge')

        asset_path = os.path.join(pf_dir, self._asset_name(self.chara))
        assert os.path.exists(asset_path), f'file {asset_path} not found'
        env = UnityPy.load(asset_path)
        
        print('[INFO] Asset bundle:', asset_path)

        tex2d: List[Texture2D] = [_.read() for _ in env.objects if _.type.name == 'Texture2D']
        [_.image.save(os.path.join(pf_dir, _.m_Name + '.png')) for _ in tex2d]

        main = np.empty((*base['m_SizeDelta'].astype(np.int32)[::-1], 4), dtype=np.uint8)
        for _, _, files in os.walk(pf_dir):
            for img in [_ for _ in files if _.endswith('.png')]:
                print(os.path.join(pf_dir, img))
                diff = read_img(os.path.join(pf_dir, img))
                main[y:y + h, x:x + w] = diff[:, :]
                save_img(main, os.path.join(pf_dir + '-merge', img))


class SplitHelper(TextureHelper):
    def split(self):
        _, face, x, y, w, h = get_rect_transform(os.path.join(self.dir, self._asset_name(self.chara)))

        pf_dir = os.path.join(self.dir, 'paintingface')
        if not os.path.exists(pf_dir + '-split'):
            os.mkdir(pf_dir + '-split')

        main = np.empty((*face['m_SizeDelta'].astype(np.int32)[::-1], 4), dtype=np.uint8)
        for _, _, files in os.walk(pf_dir + '-merge'):
            for img in [_ for _ in files if _.endswith('.png')]:
                print(os.path.join(pf_dir + '-merge', img))
                full = read_img(os.path.join(pf_dir + '-merge', img))
                main[:, :] = full[y:y + h, x:x + w]
                save_img(main, os.path.join(pf_dir + '-split', img))
