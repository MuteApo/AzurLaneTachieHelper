"""Write exact Unity objects, combining edits before saving each source bundle once."""

import logging
import shutil
import struct
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from tempfile import mkdtemp
from typing import cast
from uuid import uuid4

import UnityPy
from PIL import Image
from UnityPy.enums import ClassIDType, TextureFormat

from adapters.unity.index import project_root
from adapters.unity.transforms import transform_node
from domain.imaging import layer_placement, sample_image
from domain.messages import QT_TRANSLATE_NOOP, Message, Progress, no_progress
from domain.model import FaceMode, Kind, ObjectRef, Placement, Point, Project

logger = logging.getLogger(__name__)


def _quad(data, size, endian, *, pivot=(0.0, 0.0), units=1.0):
    """Replace the atlas mesh with a full-image quad and explicit float32 channels."""
    w, h = size
    x, y = -w * pivot[0] / units, -h * pivot[1] / units
    w, h = w / units, h / units
    values = (x, y, 0, 0, 0, x, y + h, 0, 0, 1, x + w, y + h, 0, 1, 1, x + w, y, 0, 1, 0)
    vertex = data["m_VertexData"]
    channels = vertex["m_Channels"]
    for channel in channels:
        channel.update(stream=0, offset=0, format=0, dimension=0)
    channels[0].update(dimension=3)
    channels[4].update(offset=12, dimension=2)
    vertex["m_DataSize"] = struct.pack(endian + "20f", *values)
    vertex["m_VertexCount"] = 4
    data["m_IndexBuffer"] = list(struct.pack(endian + "6H", 0, 1, 2, 2, 3, 0))
    bounds = {
        "m_Center": {"x": x + w / 2, "y": y + h / 2, "z": 0.0},
        "m_Extent": {"x": w / 2, "y": h / 2, "z": 0.0},
    }
    submesh = data["m_SubMeshes"][0].copy()
    submesh.update(
        firstByte=0, indexCount=6, topology=0, baseVertex=0, firstVertex=0, vertexCount=4, localAABB=bounds
    )
    data["m_SubMeshes"] = [submesh]
    if "m_IndexFormat" in data:
        data["m_IndexFormat"] = 0
    if "m_LocalAABB" in data:
        data["m_LocalAABB"] = bounds
    if "m_StreamData" in data:
        data["m_StreamData"].update(offset=0, size=0, path="")


def _set_sprite(reader, image):
    data = reader.parse_as_dict()
    w, h = image.size
    data["m_Rect"].update(x=0, y=0, width=w, height=h)
    rd = data["m_RD"]
    rd["textureRect"].update(x=0, y=0, width=w, height=h)
    rd["textureRectOffset"].update(x=0, y=0)
    rd["settingsRaw"] = 0  # standalone, unrotated, full-rect sprite
    pivot = data.get("m_Pivot", {"x": 0.5, "y": 0.5})
    units = data["m_PixelsToUnits"]
    rd["uvTransform"].update(x=units, y=w * pivot["x"], z=units, w=h * pivot["y"])
    # Preserve the texture reference, but discard tight geometry from the old image.
    _quad(rd, image.size, reader.reader.endian, pivot=(pivot["x"], pivot["y"]), units=units)
    reader.patch(data)


def _resize_rects(env, targets: dict[int, Placement]):
    """Resize selected rects without shifting their unedited children or siblings.

    Anchors depend on parent size. Recompute anchored positions from world-space
    geometry rather than copying another layer's pivot, which fails with scaling.
    """
    roots = [
        p.deref_parse_as_object() for p in env.file.container.values() if p.type == ClassIDType.GameObject
    ]
    pointers = [
        c.component
        for c in roots[0].m_Component
        if c.component.type in (ClassIDType.RectTransform, ClassIDType.Transform)
    ]

    def visit(pointer, old_parent=None, new_parent=None, shift=(0.0, 0.0)):
        transform = pointer.deref_parse_as_object()
        old = transform_node(transform, old_parent)
        desired = targets.get(transform.object_reader.path_id, old.placement())
        origin, size = desired.origin, desired.size
        pivot = old.pivot
        if old_parent is None:
            shift = origin
            if transform.object_reader.path_id in targets:
                # The prefab's external anchor is outside this project. Keep its
                # pivot position stable while moving the image bounds around it.
                pivot = cast(Point, tuple((old.pivot_position[i] - origin[i]) / size[i] for i in range(2)))
        origin = tuple(origin[i] - shift[i] for i in range(2))
        desired = replace(desired, origin=origin, pivot=pivot)
        pivot_pos = desired.mapping((1, 1)).point(pivot)
        local_size = tuple(size[i] / old.scale[i] for i in range(2))
        current = replace(
            old,
            parent=new_parent,
            local_size=local_size,
            matrix=replace(old.matrix, x=pivot_pos[0], y=pivot_pos[1]),
            pivot=pivot,
        )
        data = transform.object_reader.parse_as_dict()
        parent_changed = (
            old_parent
            and new_parent
            and (
                old_parent.matrix != new_parent.matrix
                or old_parent.local_size != new_parent.local_size
                or old_parent.pivot != new_parent.pivot
            )
        )
        geometry_changed = origin != old.origin or size != old.size or pivot != old.pivot or parent_changed
        if geometry_changed and "m_SizeDelta" in data:
            local_position = new_parent.matrix.inverse().point(pivot_pos) if new_parent else (0.0, 0.0)
            for i, axis in enumerate(("x", "y")):
                data["m_Pivot"][axis] = pivot[i]
                anchor_min = data["m_AnchorMin"][axis]
                anchor_max = data["m_AnchorMax"][axis]
                stretch = anchor_max - anchor_min
                parent_size = (
                    new_parent.local_size[i]
                    if new_parent and hasattr(new_parent.transform, "m_SizeDelta")
                    else 0
                )
                data["m_SizeDelta"][axis] = local_size[i] - stretch * parent_size
                if new_parent:
                    anchor = parent_size * (anchor_min + stretch * pivot[i] - new_parent.pivot[i])
                    data["m_AnchoredPosition"][axis] = local_position[i] - anchor
                    data["m_LocalPosition"][axis] = local_position[i]
            # Leave untouched rect objects byte-for-byte intact when nothing moved.
            original = transform.object_reader.parse_as_dict()
            if data != original:
                transform.object_reader.patch(data)
        elif geometry_changed and new_parent:
            local_position = new_parent.matrix.inverse().point(pivot_pos)
            for i, axis in enumerate(("x", "y")):
                data["m_LocalPosition"][axis] = local_position[i]
            if data != transform.object_reader.parse_as_dict():
                transform.object_reader.patch(data)
        for child in transform.m_Children:
            visit(child, old, current, shift)

    visit(pointers[0])


class UnityWriter:
    def export(self, project: Project, destination: Path, progress: Progress = no_progress) -> list[Path]:
        if not project.modified:
            raise ValueError(
                Message(
                    QT_TRANSLATE_NOOP(
                        "Messages", "There are no edits to export. Import images or create portraits first."
                    )
                )
            )
        environments = {}
        readers = {}
        root = project_root(project.metadata)

        def environment(path):
            if path not in environments:
                environments[path] = UnityPy.load(str(path))
                for reader in environments[path].objects:
                    readers[ObjectRef(path, reader.assets_file.name, reader.path_id)] = reader
            return environments[path]

        def get(ref):
            environment(ref.bundle)
            try:
                return readers[ref]
            except KeyError as error:
                raise ValueError(
                    Message(
                        QT_TRANSLATE_NOOP(
                            "Messages", "A resource object has changed. Reopen the project: {0} / {1}"
                        ),
                        (
                            ref.bundle.name,
                            ref.path_id,
                        ),
                    )
                ) from error

        images = {a.key: a.replacement for a in project.assets if a.replacement is not None}
        targets = {}
        if project.face and project.options.face_mode != FaceMode.OFF:
            faces = [a for a in project.modified if a.kind == Kind.FACE]
            boxes = {a.replacement_box for a in faces}
            if len(boxes) > 1:
                raise ValueError(
                    Message(
                        QT_TRANSLATE_NOOP(
                            "Messages",
                            "Expression crop bounds differ. Use full-canvas images with matching dimensions.",
                        )
                    )
                )
            if faces and faces[0].replacement_box:
                box = faces[0].replacement_box
                original_box = project.face.box(project.bias)
                if box != original_box:
                    expanded = layer_placement(project, faces[0])
                    targets[cast(ObjectRef, project.face.rect).path_id] = expanded
                    # All expressions share one RectTransform; retain unchanged ones
                    # at their original position when the shared frame is expanded.
                    for asset in project.assets:
                        if asset.kind == Kind.FACE and not asset.modified:
                            size = images[faces[0].key].size
                            mapping = project.face.mapping(asset.original.size).inverse() @ expanded.mapping(
                                size
                            )
                            images[asset.key] = sample_image(asset.original, size, mapping)

        texture_edits = {}
        work = [a for a in project.assets if a.key in images]
        for index, asset in enumerate(work):
            progress(Message(QT_TRANSLATE_NOOP("Messages", "Encoding {0}"), (asset.name,)), index, len(work))
            image = images[asset.key]
            previous = texture_edits.get(asset.texture)
            if previous is not None and previous.tobytes() != image.tobytes():
                raise ValueError(
                    Message(
                        QT_TRANSLATE_NOOP(
                            "Messages", "Multiple layers edit the same texture with conflicting content: {0}"
                        ),
                        (asset.name,),
                    )
                )
            texture_edits[asset.texture] = image
            texture = get(asset.texture).parse_as_object()
            texture.set_image(image.transpose(Image.Transpose.FLIP_TOP_BOTTOM), TextureFormat.RGBA32)
            texture.save()
            if asset.sprite:
                _set_sprite(get(asset.sprite), image)
            if asset.mesh:
                mesh = get(asset.mesh)
                data = mesh.parse_as_dict()
                _quad(data, image.size, mesh.reader.endian)
                mesh.patch(data)
            if asset.kind == Kind.PAINTING:
                if asset.behaviour and image.size != asset.raw_size:
                    behaviour = get(asset.behaviour)
                    data = behaviour.parse_as_dict()
                    if "mRawSpriteSize" in data:
                        data["mRawSpriteSize"].update(x=image.width, y=image.height)
                        behaviour.patch(data)
                if project.options.face_mode == FaceMode.CUSTOM and asset.replacement_box:
                    rect = cast(ObjectRef, cast(Placement, asset.placement).rect)
                    targets[rect.path_id] = layer_placement(project, asset)

        if targets:
            _resize_rects(environment(project.metadata), targets)
        destination.mkdir(parents=True, exist_ok=True)
        staging = Path(mkdtemp(prefix=".tachie-", dir=destination))
        name = f"{project.metadata.name}-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:6]}"
        final = destination / name
        paths = []
        try:
            for index, (source, env) in enumerate(environments.items()):
                progress(
                    Message(QT_TRANSLATE_NOOP("Messages", "Writing {0}"), (source.name,)),
                    index,
                    len(environments),
                )
                relative = (
                    Path("painting") / source.name if source == project.metadata else source.relative_to(root)
                )
                output = staging / relative
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(env.file.save(project.options.compression))
                paths.append(final / relative)
            progress(
                Message(QT_TRANSLATE_NOOP("Messages", "Asset export complete")),
                len(environments),
                len(environments),
            )
            staging.rename(final)
        except BaseException:
            if staging.resolve().parent == destination.resolve():
                shutil.rmtree(staging)
            raise
        logger.info("已导出 %d 个资源包到 %s", len(paths), final)
        return paths
