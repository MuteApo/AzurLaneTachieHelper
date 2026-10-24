"""Bounded Pillow thumbnail caching; no Qt objects or display dependencies."""

from collections import OrderedDict
from dataclasses import dataclass
from weakref import ReferenceType, ref

from PIL import Image, ImageOps

from domain.imaging import display_layer, upright
from domain.model import Kind, Project


@dataclass
class _Thumbnail:
    source: ReferenceType[Image.Image]
    image: Image.Image


class ThumbnailCache:
    """Prepare PIL thumbnails on the existing worker; Qt images stay on the UI thread.

    One cache belongs to one session. Sources are immutable session images; weak
    references avoid keeping full-sized images alive for a tiny sidebar preview.
    """

    def __init__(self, size: int):
        self._size = size
        self._images: OrderedDict[str, _Thumbnail] = OrderedDict()
        self._limit = 256  # At 144 px, at most 20.25 MiB of RGBA thumbnails.

    def clear(self) -> None:
        self._images.clear()

    def prepare(self, project: Project) -> dict[str, Image.Image]:
        thumbnails = {}
        for asset in project.assets:
            source = asset.replacement or asset.mesh_image or asset.original
            cached = self._images.get(asset.key)
            if cached is None or cached.source() is not source:
                pixels = asset.image() if asset.kind == Kind.ICON else display_layer(project, asset)[0]
                image = upright(ImageOps.contain(pixels, (self._size, self._size), Image.Resampling.LANCZOS))
                cached = _Thumbnail(ref(source), image)
                self._images[asset.key] = cached
            self._images.move_to_end(asset.key)
            thumbnails[asset.key] = cached.image
            while len(self._images) > self._limit:
                self._images.popitem(last=False)
        for key in self._images.keys() - thumbnails.keys():
            del self._images[key]
        return thumbnails
