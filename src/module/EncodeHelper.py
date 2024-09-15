import os
import struct
from typing import Literal

import UnityPy
from PIL import Image
from rich.progress import Progress
from UnityPy.classes import Mesh, RectTransform, Sprite, Texture2D
from UnityPy.enums import ClassIDType, TextureFormat

from ..base import FaceLayer, IconLayer, Layer
from ..utility import check_and_save


def set_sprite(sprite: Sprite, img: Image.Image):
    sprite.m_Rect.width, sprite.m_Rect.height = img.size
    sprite.m_RD.textureRect.width, sprite.m_RD.textureRect.height = img.size
    sprite.save()


def set_tex2d(tex2d: Texture2D, img: Image.Image):
    tex2d.m_Width, tex2d.m_Height = img.size
    tex2d.set_image(img.transpose(Image.Transpose.FLIP_TOP_BOTTOM), TextureFormat.RGBA32)
    tex2d.save()


def set_mesh(mesh: Mesh, img: Image.Image):
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


class EncodeHelper:
    @staticmethod
    def replace_painting(dir: str, layer: Layer) -> str:
        """
        Replace painting and save for a tachie `Layer`.

        Parameters
        ----------
        dir: str
            Root directory for output.
        layer: Layer
            The target `Layer`.

        Returns
        -------
        path: str
            Path to the saved file.
        """

        path = layer.path if layer.path != "Not Found" else layer.meta.path
        env = UnityPy.load(path)

        for x in env.objects:
            if x.type == ClassIDType.Texture2D:
                set_tex2d(x.read(), layer.repl)
            elif x.type == ClassIDType.Mesh:
                set_mesh(x, layer.repl)

        path = os.path.join(dir, "output", "painting", os.path.basename(path))
        check_and_save(path, env.file.save("lzma"))

        return path

    @staticmethod
    def replace_meta(dir: str, layer: Layer, prefered: Layer) -> str:
        """
        Replace metadata and save for advanced paintingface mode.

        Parameters
        ----------
        dir: str
            Root directory for output.
        layer: Layer
            The target `Layer` for paintingface.
        prefered: Layer
            The prefered `Layer` for enlarged paintingface.

        Returns
        -------
        path: str
            Path to the saved file.
        """

        env = UnityPy.load(layer.meta.path)
        cab = list(env.cabs.values())[0]
        face_rt: RectTransform = cab.objects[layer.pathId]
        data = face_rt.read_typetree()
        data["m_SizeDelta"] = prefered.sizeDelta.dict()
        data["m_Pivot"] = prefered.pivot.dict()
        data["m_AnchoredPosition"] = (prefered.pivotPosition - layer.anchorPosition).dict()
        face_rt.save_typetree(data)

        path = os.path.join(dir, "output", "painting", os.path.basename(layer.meta.path))
        check_and_save(path, env.file.save("lzma"))

        return [path]

    @staticmethod
    def replace_face(dir: str, faces: dict[str, FaceLayer], progress: Progress) -> list[str]:
        """
        Replace paintingface and save for a tachie `FaceLayer`.

        Parameters
        ----------
        dir: str
            Root directory for output.
        faces: dict[str, FaceLayer]
            The dict containing each of the paintingface images, as pseudo-layers.
        progress: Progress
            The rich progress bar.

        Returns
        -------
        path: list[str]
            Paths to the saved files.
        """

        first = list(faces.values())[0]
        layer = first.layer
        prefered = first.prefered
        adv_mode = first.adv_mode

        base = layer.meta.name_stem
        path = os.path.join(os.path.dirname(layer.meta.path), "paintingface", base)
        env = UnityPy.load(path)

        task = progress.add_task("Encode paintingface", total=len(faces))
        for x in env.objects:
            if x.type == ClassIDType.Texture2D:
                tex2d: Texture2D = x.read()
                if tex2d.name in faces:
                    set_tex2d(x.read(), faces[tex2d.name].repl)
                    progress.update(task, advance=1)

        path = os.path.join(dir, "output", "paintingface", base)
        check_and_save(path, env.file.save("lzma"))

        if adv_mode:
            return EncodeHelper.replace_meta(dir, layer, prefered) + [path]
        else:
            return [path]

    @staticmethod
    def replace_icon(dir: str, kind: Literal["shipyardicon", "herohrzicon", "squareicon"], icon: IconLayer) -> str:
        """
        Replace icon and save for a tachie `IconLayer`.

        Parameters
        ----------
        dir: str
            Root directory for output.
        kind: Literal["shipyardicon", "herohrzicon", "squareicon"]
            The icon type.
        icon: IconLayer
            The pseudo-layer containing icon image.

        Returns
        -------
        path: str
            Path to the saved file.
        """

        env = UnityPy.load(icon.path)
        for v in env.container.values():
            set_tex2d(v.read().m_RD.texture.read(), icon.repl)

        path = os.path.join(dir, "output", kind, icon.layer.meta.name_stem)
        check_and_save(path, env.file.save("lzma"))

        return path

    @staticmethod
    def exec(dir: str, layers: dict[str, Layer], faces: dict[str, FaceLayer], icons: dict[str, IconLayer]) -> list[str]:
        """
        Decode layers of a painting along with paintingface and return file path of the dumped psd.

        Parameters
        ----------
        dir: str
            Root directory for output.
        layers: dict[str, Layer]
            The dict containing each of the painting layers.
        faces: dict[str, FaceLayer]
            The dict containing each of the paintingface images, as pseudo-layers.
        icons: dict[str, IconLayer]
            The dict containing each of the icon images, as pseudo-layers.

        Returns
        -------
        path: list[str]
            Paths to the saved files.
        """

        result = []
        with Progress() as progress:
            valid = [v for v in layers.values() if v.modified]
            if valid != []:
                task = progress.add_task("Encode painting", total=len(valid))
                for x in valid:
                    result += [EncodeHelper.replace_painting(dir, x)]
                    progress.update(task, advance=1)

            valid = {k: v for k, v in faces.items() if v.modified}
            if valid != {}:
                result += EncodeHelper.replace_face(dir, valid, progress)

            valid = {k: v for k, v in icons.items() if v.modified and os.path.exists(v.path)}
            if valid != {}:
                task = progress.add_task("Encode icon", total=len(valid))
                for k, v in valid.items():
                    result += [EncodeHelper.replace_icon(dir, k, v)]
                    progress.update(task, advance=1)

        return result
