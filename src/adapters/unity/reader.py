import logging
from pathlib import Path
from typing import cast

import UnityPy
from PIL import Image
from UnityPy import config as unity_config
from UnityPy.classes import GameObject
from UnityPy.enums import ClassIDType as ClassID
from UnityPy.files import BundleFile
from UnityPy.helpers.MeshHelper import MeshHandler

from adapters.unity.index import dependency_index, discover_manifest, project_root, safe_relative
from adapters.unity.transforms import transform_node, vector_xy
from domain.imaging import decode_mesh
from domain.messages import QT_TRANSLATE_NOOP, Message, Progress, no_progress
from domain.model import Asset, Box, Kind, ObjectRef, Placement, Project, default_presets

logger = logging.getLogger(__name__)


class UnityReader:
    """Unity objects live only while reading; the returned project contains plain data and images."""

    def load(self, metadata: Path, manifest: Path | None = None, progress: Progress = no_progress) -> Project:
        unity_config.FALLBACK_UNITY_VERSION = "2022.3.62f3"
        metadata = metadata.resolve()
        root = project_root(metadata)
        progress(Message(QT_TRANSLATE_NOOP("Messages", "Reading resource dependencies")), 0, 0)
        manifest = manifest or discover_manifest(metadata)
        index = dependency_index(manifest) if manifest else {}
        dependencies = index.get(f"painting/{metadata.name}", ())
        logger.info("打开资源 %s", metadata.name)
        env = UnityPy.load(str(metadata))
        bundles = {id(env.file): metadata}
        loaded = {metadata}

        def load_file(path: Path):
            path = path.resolve()
            if path in loaded:
                return
            bundle = env.load_file(str(path))
            bundles[id(bundle)] = path
            loaded.add(path)

        if dependencies:
            optional = {"paintingface", *default_presets()}
            missing = []
            available = []
            for name in dependencies:
                relative = safe_relative(name)
                if (root / relative).is_file():
                    available.append(name)
                elif relative.parts[0] in optional:
                    logger.warning("可选资源不可用：%s", name)
                else:
                    missing.append(name)
            if missing:
                raise FileNotFoundError(
                    Message(
                        QT_TRANSLATE_NOOP("Messages", "Project dependencies are missing:\n{0}"),
                        ("\n".join(missing),),
                    )
                )
            for i, name in enumerate(available):
                progress(Message(QT_TRANSLATE_NOOP("Messages", "Reading {0}"), (name,)), i, len(available))
                load_file(root / safe_relative(name))
        else:
            # A self-contained project can be opened without a global manifest or an Android device.
            candidates = [root / "custom_builtin"]
            for directory in (root / "painting", root / "ui"):
                if directory.is_dir():
                    candidates.extend(p for p in directory.iterdir() if p.is_file() and p.suffix != ".png")
            for path in candidates:
                if path.is_file() and path != metadata:
                    load_file(path)

        def ref(obj) -> ObjectRef:
            reader = obj.object_reader
            owner = reader.assets_file
            while id(owner) not in bundles and getattr(owner, "parent", None) is not None:
                owner = owner.parent
            if id(owner) not in bundles:
                raise ValueError(
                    Message(
                        QT_TRANSLATE_NOOP("Messages", "Cannot determine the object's resource bundle: {0}"),
                        (reader.path_id,),
                    )
                )
            return ObjectRef(bundles[id(owner)], reader.assets_file.name, reader.path_id)

        # Only select the prefab from the metadata, never a dependency's GameObject.
        metadata_bundle = cast(BundleFile, env.file)
        game_objects = [
            cast(GameObject, p.deref_parse_as_object())
            for p in metadata_bundle.container.values()
            if p.type == ClassID.GameObject
        ]
        if not game_objects:
            raise ValueError(
                Message(
                    QT_TRANSLATE_NOOP(
                        "Messages", "Select artwork metadata. This file contains no GameObject."
                    )
                )
            )
        game_object = game_objects[0]
        transforms = []
        for entry in game_object.m_Component:
            component = entry[1] if isinstance(entry, tuple) else entry.component
            if component.type in (ClassID.RectTransform, ClassID.Transform):
                transforms.append(component)
        if not transforms:
            raise ValueError(Message(QT_TRANSLATE_NOOP("Messages", "The artwork contains no Transform.")))
        assets: list[Asset] = []
        face = None
        used_keys: set[str] = set()
        texture_cache: dict[ObjectRef, Image.Image] = {}

        def texture_image(texture):
            key = ref(texture)
            if key not in texture_cache:
                texture_cache[key] = texture.image.convert("RGBA").transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            return texture_cache[key]

        def visit(pointer, parent=None, active=True):
            nonlocal face
            transform = pointer.deref_parse_as_object()
            go = transform.m_GameObject.deref_parse_as_object()
            active = active and bool(go.m_IsActive)
            node = transform_node(transform, parent)
            placement = node.placement(ref(transform))
            if go.m_Name.lower() == "face":
                face = placement
            for component in go.m_Component:
                if component.component.type != ClassID.MonoBehaviour:
                    continue
                behaviour = component.component.deref_parse_as_object()
                if not active or not behaviour.m_Enabled:
                    continue
                sprite_ptr = getattr(behaviour, "m_Sprite", None)
                if not sprite_ptr or not sprite_ptr.m_PathID or go.m_Name.lower() == "face":
                    continue
                sprite = sprite_ptr.deref_parse_as_object()
                if not sprite.m_RD.texture.m_PathID:
                    continue
                texture = sprite.m_RD.texture.deref_parse_as_object()
                name = sprite.m_Name if go.m_Name == "part" else go.m_Name
                key = name if name not in used_keys else f"{name}@{transform.object_reader.path_id}"
                used_keys.add(key)
                progress(Message(QT_TRANSLATE_NOOP("Messages", "Restoring {0}"), (name,)), len(assets), 0)
                image = texture_image(texture)
                mesh_ptr = getattr(behaviour, "mMesh", None)
                mesh = mesh_ptr.deref_parse_as_object() if mesh_ptr and mesh_ptr.m_PathID else None
                decoded = None
                if mesh:
                    handler = MeshHandler(mesh)
                    handler.process()
                    vertices, uv, indices = handler.m_Vertices, handler.m_UV0, handler.m_IndexBuffer
                    if vertices is None or uv is None or indices is None:
                        raise ValueError(
                            Message(
                                QT_TRANSLATE_NOOP(
                                    "Messages", "Mesh vertices or texture coordinates are missing: {0}"
                                ),
                                (name,),
                            )
                        )
                    decoded = decode_mesh(image, vertices, uv, indices)
                if mesh is None:
                    # Ordinary Image uses the sprite rect, not the atlas dimensions
                    # or stale MeshImage.mRawSpriteSize left after changing sprites.
                    native = sprite.image.convert("RGBA").transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                    sprite_size = round(sprite.m_Rect.width), round(sprite.m_Rect.height)
                    decoded = Image.new("RGBA", sprite_size)
                    offset = sprite.m_RD.textureRectOffset
                    decoded.paste(native, (round(offset.x), round(offset.y)))
                raw = (
                    vector_xy(getattr(behaviour, "mRawSpriteSize", None), image.size) if mesh else sprite_size
                )
                raw_size = max(1, round(raw[0])), max(1, round(raw[1]))
                assets.append(
                    Asset(
                        key,
                        name,
                        Kind.PAINTING,
                        ref(texture),
                        image,
                        placement,
                        ref(sprite),
                        ref(mesh) if mesh else None,
                        raw_size,
                        decoded.size if decoded else image.size,
                        decoded,
                        behaviour=ref(behaviour),
                        texture_name=texture.m_Name,
                        preserve_aspect=bool(behaviour.m_PreserveAspect),
                    )
                )
                break
            for child in transform.m_Children:
                visit(child, node, active)

        visit(transforms[0])
        if not assets:
            raise ValueError(
                Message(QT_TRANSLATE_NOOP("Messages", "No restorable artwork textures were found."))
            )
        placements = [a.placement for a in assets if a.placement is not None] + ([face] if face else [])
        low = tuple(min(p.bounds()[i] for p in placements) for i in range(2))
        bias = -low[0], -low[1]
        # Use the same rounded pixel edges as preview and crop. Tiny serialized
        # float offsets at an otherwise aligned edge must not add a blank row.
        boxes = [placement.box(bias) for placement in placements]
        size = max(box[2] for box in boxes), max(box[3] for box in boxes)
        base = metadata.name.removesuffix("_n")

        def extras(path: Path, kind: Kind, label: str):
            if not path.is_file():
                return
            load_file(path)
            bundle = cast(
                BundleFile, next(v for v in env.files.values() if bundles.get(id(v)) == path.resolve())
            )
            objects = list(bundle.get_objects())
            sprites = {}
            for obj in objects:
                if obj.type == ClassID.Sprite:
                    sprite = obj.parse_as_object()
                    sprites[sprite.m_RD.texture.m_PathID] = sprite
            textures = [obj.parse_as_object() for obj in objects if obj.type == ClassID.Texture2D]
            textures.sort(key=lambda t: (0, int(t.m_Name)) if t.m_Name.isdecimal() else (1, t.m_Name))
            for texture in textures:
                if kind == Kind.ICON and texture.m_Name.lower() != base.lower():
                    continue
                sprite = sprites.get(texture.object_reader.path_id)
                key = f"paintingface/{texture.m_Name}" if kind == Kind.FACE else label
                assets.append(
                    Asset(
                        key,
                        texture.m_Name if kind == Kind.FACE else label,
                        kind,
                        ref(texture),
                        texture_image(texture),
                        sprite=ref(sprite) if sprite else None,
                        texture_name=texture.m_Name,
                    )
                )

        if face:
            extras(root / "paintingface" / base, Kind.FACE, "paintingface")
        for kind in default_presets():
            path = root / kind / base
            extras(path if path.is_file() else path.with_name(path.name + ".ys"), Kind.ICON, kind)
        project = Project(metadata, game_object.m_Name, size, bias, assets, face, tuple(dependencies))
        if face:
            preferred = cast(Placement, project.preferred().placement).box(project.bias)
            project.options.extensions["paintingface"] = cast(
                Box, tuple(a - b for a, b in zip(preferred, face.box(project.bias)))
            )
        # Session restoration and the first preview still follow resource decoding.
        progress(Message(QT_TRANSLATE_NOOP("Messages", "Preparing project…")), 0, 0)
        return project
