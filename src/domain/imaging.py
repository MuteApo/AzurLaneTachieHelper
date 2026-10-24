"""All internal images use Unity's bottom-left origin. Flip only at file/UI boundaries."""

import math
from dataclasses import replace
from pathlib import Path
from typing import cast

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from domain.geometry import Affine
from domain.messages import QT_TRANSLATE_NOOP, Message
from domain.model import Asset, Box, FaceMode, IconPreset, ImageAlignment, Kind, Placement, Project


def read_image(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return ImageOps.exif_transpose(image).convert("RGBA").transpose(Image.Transpose.FLIP_TOP_BOTTOM)


def upright(image: Image.Image) -> Image.Image:
    return image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)


def align_image(image: Image.Image, size: tuple[int, int], alignment: ImageAlignment) -> Image.Image:
    """Place a bottom-left image using the import dialog's top-left coordinates.

    Integer translation preserves all pixels exactly. Scaling samples premultiplied
    alpha so transparent borders do not bleed into the artwork.
    """
    mapping = Affine(
        a=alignment.scale,
        d=alignment.scale,
        x=alignment.x,
        y=size[1] - alignment.y - image.height * alignment.scale,
    ).inverse()
    if alignment.scale == 1:
        return sample_image(image, size, mapping)
    return sample_image(image.convert("RGBa"), size, mapping).convert("RGBA")


def intersect(box: Box, size: tuple[int, int]) -> Box:
    x1, y1, x2, y2 = box
    result = max(0, x1), max(0, y1), min(size[0], x2), min(size[1], y2)
    if result[2] <= result[0] or result[3] <= result[1]:
        raise ValueError(
            Message(
                QT_TRANSLATE_NOOP(
                    "Messages",
                    "The crop does not overlap the image. Check canvas dimensions and boundary offsets.",
                )
            )
        )
    return result


def replacement_bounds(project: Project, asset: Asset) -> Box | None:
    """Requested canvas bounds, before clipping to an imported image.

    The preview shows this full rectangle so an out-of-canvas edge remains
    adjustable. Importing uses the same bounds, then applies its clipping rule.
    """
    if asset.kind == Kind.ICON:
        return None
    placement = asset.placement if asset.kind == Kind.PAINTING else project.face
    if placement is None:
        return None
    box = placement.box(project.bias)
    mode = project.options.face_mode
    if asset.kind == Kind.FACE and mode == FaceMode.AUTO:
        box = cast(Placement, project.preferred().placement).box(project.bias)
    elif mode == FaceMode.CUSTOM:
        key = "paintingface" if asset.kind == Kind.FACE else asset.key
        extension = project.options.extensions.get(key, (0, 0, 0, 0))
        box = cast(Box, tuple(a + b for a, b in zip(box, extension)))
    return box


def replacement_box(project: Project, asset: Asset, source: Image.Image) -> Box:
    box = replacement_bounds(project, asset)
    if box is None:
        raise ValueError(
            Message(QT_TRANSLATE_NOOP("Messages", "Positioning information is missing for this asset."))
        )
    mode = project.options.face_mode
    # Off mode pads transparent pixels, preserving the original rect and pivot.
    if mode == FaceMode.OFF or (mode == FaceMode.AUTO and asset.kind == Kind.PAINTING):
        return box
    return intersect(box, source.size)


def layer_placement(project: Project, asset: Asset) -> Placement:
    placement = asset.placement if asset.kind == Kind.PAINTING else project.face
    if placement is None:
        raise ValueError(
            Message(QT_TRANSLATE_NOOP("Messages", "Missing layer placement: {0}"), (asset.name,))
        )
    if asset.replacement_box and (
        project.options.face_mode == FaceMode.CUSTOM
        or (asset.kind == Kind.FACE and project.options.face_mode == FaceMode.AUTO)
    ):
        return placement.reframe(asset.replacement_box, project.bias)
    return placement


def drawing_placement(placement: Placement, image_size: tuple[int, int], preserve_aspect: bool) -> Placement:
    if not preserve_aspect:
        return placement
    # Unity applies preserveAspect in the unscaled local rect and aligns the
    # remaining space using its pivot, before applying the Transform chain.
    factor = min(placement.size[i] / placement.scale[i] / image_size[i] for i in range(2))
    size = tuple(image_size[i] * factor * placement.scale[i] for i in range(2))
    offset = tuple((1 - size[i] / placement.size[i]) * placement.pivot[i] for i in range(2))
    origin = placement.mapping((1, 1)).point(cast(tuple[float, float], offset))
    return replace(placement, origin=origin, size=cast(tuple[float, float], size))


def render_placement(image: Image.Image, placement: Placement, bias=(0.0, 0.0)) -> tuple[Image.Image, Box]:
    box = placement.box(bias)
    size = box[2] - box[0], box[3] - box[1]
    inverse = placement.mapping(image.size, bias).inverse() @ Affine(x=box[0], y=box[1])
    return sample_image(image, size, inverse), box


def sample_image(image: Image.Image, size: tuple[int, int], mapping: Affine) -> Image.Image:
    # Integer translations are exact copies, including RGB under transparent
    # pixels. Ignore only arithmetic noise from composing/inverting matrices.
    values = (
        mapping.a - 1,
        mapping.b,
        mapping.c,
        mapping.d - 1,
        mapping.x - round(mapping.x),
        mapping.y - round(mapping.y),
    )
    if all(abs(value) < 1e-8 for value in values):
        x, y = round(mapping.x), round(mapping.y)
        return image.crop((x, y, x + size[0], y + size[1]))
    return image.transform(size, Image.Transform.AFFINE, mapping.pillow(), Image.Resampling.BICUBIC)


def prepare_replacement(
    project: Project, asset: Asset, source: Image.Image
) -> tuple[Image.Image, Box | None]:
    if asset.kind == Kind.ICON:
        return source.resize(asset.original.size, Image.Resampling.LANCZOS), None
    box = replacement_box(project, asset, source)
    placement = asset.placement if asset.kind == Kind.PAINTING else project.face
    assert placement is not None  # replacement_box requires a positioned asset
    resized = project.options.face_mode == FaceMode.CUSTOM or (
        asset.kind == Kind.FACE and project.options.face_mode == FaceMode.AUTO
    )
    if resized:
        placement = placement.reframe(box, project.bias)
    target = max(1, round(placement.size[0])), max(1, round(placement.size[1]))
    if asset.preserve_aspect and resized:
        target = (
            max(1, round(placement.size[0] / placement.scale[0])),
            max(1, round(placement.size[1] / placement.scale[1])),
        )
    if asset.kind == Kind.PAINTING and project.options.face_mode != FaceMode.CUSTOM:
        target = asset.raw_size or asset.original.size
    draw = drawing_placement(placement, target, asset.preserve_aspect)
    mapping = draw.mapping(target, project.bias)
    if resized:
        # Rotated rects enclose extra corners outside the requested canvas crop.
        source = source.crop(box)
        mapping = Affine(x=-box[0], y=-box[1]) @ mapping
    result = sample_image(source, target, mapping)
    return result, box


def decode_mesh(texture: Image.Image, vertices: list, uv: list, indices: list) -> Image.Image:
    """Fast rectangular atlas patches, with an affine triangle path for other meshes.

    Quad recognition uses vertex positions instead of relying on a particular winding.
    """
    if not vertices or len(indices) % 3:
        raise ValueError(Message(QT_TRANSLATE_NOOP("Messages", "Invalid Unity triangle mesh")))
    points = [(round(v[0]), round(v[1])) for v in vertices]
    coords = [(u * texture.width, v * texture.height) for u, v, *_ in uv]
    size = max(p[0] for p in points), max(p[1] for p in points)
    if min(size) <= 0:
        raise ValueError(Message(QT_TRANSLATE_NOOP("Messages", "Mesh dimensions must be positive")))
    quads, triangles = [], []
    offset = 0
    while offset < len(indices):
        pair = indices[offset : offset + 6]
        corners = {points[i]: coords[i] for i in pair}
        xs, ys = {p[0] for p in corners}, {p[1] for p in corners}
        if len(pair) == 6 and len(corners) == 4 and len(xs) == len(ys) == 2:
            left, right = sorted(xs)
            bottom, top = sorted(ys)
            order = [(left, bottom), (left, top), (right, top), (right, bottom)]
            quads.append(((left, bottom, right, top), tuple(c for p in order for c in corners[p])))
            offset += 6
        else:
            triangles.append(indices[offset : offset + 3])
            offset += 3
    image = texture.transform(size, Image.Transform.MESH, quads, Image.Resampling.BICUBIC)
    for triangle in triangles:
        dst = np.array([points[i] for i in triangle], dtype=float)
        src = np.array([coords[i] for i in triangle], dtype=float)
        matrix = np.column_stack((dst, np.ones(3)))
        if abs(np.linalg.det(matrix)) < 1e-8:
            continue
        transform = np.linalg.solve(matrix, src).T.flatten()
        bounds = (
            max(0, int(dst[:, 0].min())),
            max(0, int(dst[:, 1].min())),
            min(size[0], int(dst[:, 0].max()) + 1),
            min(size[1], int(dst[:, 1].max()) + 1),
        )
        if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
            continue
        a, b, c, d, e, f = transform
        transform = a, b, c + a * bounds[0] + b * bounds[1], d, e, f + d * bounds[0] + e * bounds[1]
        patch_size = bounds[2] - bounds[0], bounds[3] - bounds[1]
        patch = texture.transform(patch_size, Image.Transform.AFFINE, transform, Image.Resampling.BICUBIC)
        mask = Image.new("L", patch_size)
        ImageDraw.Draw(mask).polygon([(x - bounds[0], y - bounds[1]) for x, y in dst], fill=255)
        image.paste(patch, bounds[:2], mask)
    return image


def display_layer(project: Project, asset: Asset) -> tuple[Image.Image, Box]:
    """Return pixels and canvas placement shared by preview and PSD export."""
    image = asset.image()
    placement = drawing_placement(layer_placement(project, asset), image.size, asset.preserve_aspect)
    return render_placement(image, placement, project.bias)


def composite(project: Project, face_key: str | None = None) -> Image.Image:
    canvas = Image.new("RGBA", project.size)
    for asset in project.assets:
        if asset.kind == Kind.PAINTING or asset.key == face_key:
            image, box = display_layer(project, asset)
            canvas.alpha_composite(image, box[:2])
    return canvas


def clip_icon(
    source: Image.Image, center: tuple[float, float], preset: IconPreset, shadow=False
) -> Image.Image:
    """Sample directly into the output frame, so rotations never need padded full canvases."""
    if preset.scale <= 0:
        raise ValueError(Message(QT_TRANSLATE_NOOP("Messages", "Scale must be greater than zero.")))
    width, height = preset.size
    x = center[0] - width / preset.scale * preset.pivot[0]
    y = center[1] - height / preset.scale * preset.pivot[1]
    cx, cy = x + width / preset.scale / 2, y + height / preset.scale / 2
    angle = math.radians(preset.angle)
    cos, sin = math.cos(angle), math.sin(angle)
    # PIL rotation's inverse mapping; output and source are both bottom-left images.
    matrix = (
        cos / preset.scale,
        -sin / preset.scale,
        cx + cos * (x - cx) - sin * (y - cy),
        sin / preset.scale,
        cos / preset.scale,
        cy + sin * (x - cx) + cos * (y - cy),
    )
    # A cached premultiplied source avoids reconverting the full artwork on each
    # interactive frame. Convert only the small sampled output back to straight RGBA.
    image = source.transform(preset.size, Image.Transform.AFFINE, matrix, Image.Resampling.BICUBIC).convert(
        "RGBA"
    )
    if shadow:
        a, b, c, d, e, f = matrix
        displaced = source.transform(
            preset.size,
            Image.Transform.AFFINE,
            (a, b, c + 10 * a, d, e, f + 10 * d),
            Image.Resampling.BICUBIC,
        )
        base = Image.new("RGBA", preset.size)
        base.putalpha(displaced.getchannel(3).point([min(value, 76) for value in range(256)]))
        base.alpha_composite(image)
        image = base
    return image
