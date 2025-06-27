import os
import struct
from typing import Literal

import UnityPy
from PIL import Image
from rich.progress import Progress
from UnityPy.classes import Sprite, Texture2D
from UnityPy.enums import ClassIDType, TextureFormat
from UnityPy.files import ObjectReader

from ..base import Config
from ..base.Data import FaceModeType
from ..base.Layer import FaceLayer, IconLayer, Layer
from ..base.Vector import Vector2
from ..utility import check_and_save


def set_sprite(sprite: Sprite, img: Image.Image):
    sprite.m_Rect.width, sprite.m_Rect.height = img.size
    sprite.m_RD.textureRect.width, sprite.m_RD.textureRect.height = img.size
    sprite.save()


def set_tex2d(tex2d: Texture2D, img: Image.Image):
    fmt = {"RGB": TextureFormat.RGB24, "RGBA": TextureFormat.RGBA32}[img.mode]
    tex2d.set_image(img.transpose(Image.Transpose.FLIP_TOP_BOTTOM), fmt)
    tex2d.save()


def set_mesh(mesh: ObjectReader, img: Image.Image):
    data = mesh.read_typetree()

    data["m_SubMeshes"][0]["indexCount"] = 6
    data["m_SubMeshes"][0]["vertexCount"] = 4
    data["m_IndexBuffer"] = [0, 0, 1, 0, 2, 0, 2, 0, 3, 0, 0, 0]
    data["m_VertexData"]["m_VertexCount"] = 4

    w, h = img.size
    buf = [0, 0, 0, 0, 0, 0, h, 0, 0, 1, w, h, 0, 1, 1, w, 0, 0, 1, 0]
    data_size = struct.pack(mesh.reader.endian + "f" * 20, *buf)
    data["m_VertexData"]["m_DataSize"] = memoryview(data_size)

    mesh.save_typetree(data)


def set_meta(reader: ObjectReader, size_delta: Vector2, pivot: Vector2, anchored_position: Vector2):
    data = reader.read_typetree()
    data["m_SizeDelta"] = size_delta.dict()
    data["m_Pivot"] = pivot.dict()
    data["m_AnchoredPosition"] = anchored_position.dict()
    reader.save_typetree(data)


class EncodeHelper:
    @staticmethod
    def replace_painting(dir: str, layer: Layer, reader: ObjectReader) -> tuple[str, bool]:
        path = layer.path if layer.path != "Not Found" else layer.meta.path
        env = UnityPy.load(path)

        for x in env.objects:
            match x.type:
                # case ClassIDType.Sprite:
                #     set_sprite(x.read(), layer.repl)
                case ClassIDType.Texture2D:
                    set_tex2d(x.read(), layer.repl)
                case ClassIDType.Mesh:
                    set_mesh(x, layer.repl)

        path = os.path.join(dir, "output", "painting", os.path.basename(path))
        check_and_save(path, env.file.save(Config.get_compression()))

        if Config.get_face_mode() != FaceModeType.Custom:
            return path, False

        x1, y1, _, _ = Config.get_face_extension(layer.meta.name_stem, layer.name)
        pivot = layer.pivot - Vector2(x1, y1) / layer.sizeDelta
        set_meta(reader, layer.sizeDelta, pivot, layer.anchoredPosition)

        return path, True

    @staticmethod
    def replace_face(
        dir: str, faces: dict[str, FaceLayer], reader: ObjectReader, progress: Progress
    ) -> tuple[str, bool]:
        first = list(faces.values())[0]
        layer = first.layer
        face_mode = Config.get_face_mode()

        name = layer.meta.name_stem
        path = os.path.join(os.path.dirname(layer.meta.path), "paintingface", name)
        env = UnityPy.load(path)

        cur, cnt = 0, len(faces)
        task = progress.add_task(f"Encode paintingface ({cur}/{cnt}):", total=cnt)
        for x in env.objects:
            if x.type == ClassIDType.Sprite:
                sprite: Sprite = x.read()
                if sprite.m_Name in faces:
                    if face_mode != FaceModeType.Off:
                        set_sprite(sprite, faces[sprite.m_Name].repl)
                    set_tex2d(sprite.m_RD.texture.read(), faces[sprite.m_Name].repl)
                    cur += 1
                    progress.update(task, advance=1, description=f"Encode paintingface ({cur}/{cnt}):")

        path = os.path.join(dir, "output", "paintingface", name)
        check_and_save(path, env.file.save(Config.get_compression()))

        if face_mode == FaceModeType.Off:
            return path, False

        if face_mode == FaceModeType.Auto:
            prefered = first.prefered
            size_delta = prefered.sizeDelta
            pivot = prefered.pivot
            anchored_position = prefered.pivotPosition - layer.pivotPosition + layer.anchoredPosition
        elif face_mode == FaceModeType.Custom:
            size_delta = Vector2(first.repl.size)
            x1, y1, _, _ = Config.get_face_extension(name, "paintingface")
            pivot = (layer.sizeDelta * layer.pivot - Vector2(x1, y1)) / size_delta
            anchored_position = layer.anchoredPosition

        set_meta(reader, size_delta, pivot, anchored_position)

        return path, True

    @staticmethod
    def replace_icon(dir: str, kind: Literal["shipyardicon", "herohrzicon", "squareicon"], icon: IconLayer) -> str:
        env = UnityPy.load(icon.path)
        for v in env.container.values():
            sprite: Sprite = v.read()
            set_sprite(sprite, icon.repl)
            set_tex2d(sprite.m_RD.texture.read(), icon.repl)

        path = os.path.join(dir, "output", kind, icon.layer.meta.name_stem)
        check_and_save(path, env.file.save(Config.get_compression()))

        return path

    @staticmethod
    def exec(dir: str, layers: dict[str, Layer], faces: dict[str, FaceLayer], icons: dict[str, IconLayer]) -> list[str]:
        meta_path = list(layers.values())[0].meta.path
        meta_env = UnityPy.load(meta_path)
        readers = list(meta_env.cabs.values())[0].objects
        adv_mode = False
        result = []
        with Progress() as progress:
            valid = [v for v in layers.values() if v.modified]
            if valid != []:
                cur, cnt = 0, len(valid)
                task = progress.add_task(f"Encode painting ({cur}/{cnt}):", total=cnt)
                for x in valid:
                    sub, flag = EncodeHelper.replace_painting(dir, x, readers[x.pathId])
                    result += [sub]
                    adv_mode |= flag
                    cur += 1
                    progress.update(task, advance=1, description=f"Encode painting ({cur}/{cnt}):")

            valid = {k: v for k, v in faces.items() if v.modified}
            if valid != {}:
                face_layer = list(valid.values())[0].layer
                sub, flag = EncodeHelper.replace_face(dir, valid, readers[face_layer.pathId], progress)
                result += [sub]
                adv_mode |= flag

            valid = {k: v for k, v in icons.items() if v.modified and os.path.exists(v.path)}
            if valid != {}:
                cur, cnt = 0, len(valid)
                task = progress.add_task(f"Encode icon ({cur}/{cnt}):", total=cnt)
                for k, v in valid.items():
                    result += [EncodeHelper.replace_icon(dir, k, v)]
                    cur += 1
                    progress.update(task, advance=1, description=f"Encode icon ({cur}/{cnt}):")

        if adv_mode:
            path = os.path.join(dir, "output", "painting", os.path.basename(meta_path))
            check_and_save(path, meta_env.file.save(Config.get_compression()))
            result += [path]

        return result
