"""Optional real-resource regressions: fixtures remain outside version control."""

import hashlib
import math
import shutil
from pathlib import Path

import pytest
import UnityPy
from PIL import Image, ImageDraw
from psd_tools import PSDImage
from psd_tools.constants import Compression, Resource

from adapters.psd import export_psd
from adapters.unity.index import _dependency_index, dependency_index
from adapters.unity.reader import UnityReader
from adapters.unity.transforms import transform_node
from adapters.unity.writer import UnityWriter, _resize_rects
from domain.imaging import display_layer, prepare_replacement, read_image, upright
from domain.model import Asset, FaceMode, Kind, ObjectRef, Placement, Project

RESOURCES = Path(__file__).resolve().parents[1] / "projects"


def test_dependency_index_before_opening_any_project(monkeypatch):
    manifest = RESOURCES.parent / "dependencies"
    if not manifest.is_file():
        pytest.skip("本地 dependencies 不存在")
    monkeypatch.setattr(UnityPy.config, "FALLBACK_UNITY_VERSION", None)
    _dependency_index.cache_clear()
    index = dependency_index(manifest)
    assert any(name.startswith("painting/") and dependencies for name, dependencies in index.items())


@pytest.fixture
def project():
    metadata = RESOURCES / "2b_2" / "2b_2"
    if not metadata.is_file():
        pytest.skip("本地真实资源 projects/2b_2 不存在")
    return UnityReader().load(metadata)


def _bundle_objects(path):
    env = UnityPy.load(str(path))
    return {(r.assets_file.name, r.path_id): r.get_raw_data() for r in env.objects}


def _complete_export(project, outputs):
    """Copy untouched dependencies into the temporary export for a full reopen."""
    run = outputs[0].parent.parent
    source = project.metadata.parent
    for directory in ("painting", "paintingface", "ui", "shipyardicon", "herohrzicon", "squareicon"):
        for path in (source / directory).glob("*"):
            target = run / directory / path.name
            if path.is_file() and not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
    builtin = source / "custom_builtin"
    if builtin.is_file():
        shutil.copyfile(builtin, run / "custom_builtin")
    metadata = run / "painting" / project.metadata.name
    if not metadata.exists():
        shutil.copyfile(project.metadata, metadata)
    return UnityReader().load(metadata)


def test_same_bundle_faces_preserve_other_objects_and_source(project, tmp_path):
    faces = [a for a in project.assets if a.kind == Kind.FACE]
    source = faces[0].texture.bundle
    digest = hashlib.sha256(source.read_bytes()).digest()
    before = _bundle_objects(source)
    changed = set()
    for index, asset in enumerate(faces[:2]):
        asset.replacement = Image.new("RGBA", asset.original.size, (20 + index * 40, 70, 90, 255))
        for ref in (asset.texture, asset.sprite):
            changed.add((ref.cabinet, ref.path_id))
    outputs = UnityWriter().export(project, tmp_path)
    assert len(outputs) == 1
    after = _bundle_objects(outputs[0])
    assert before.keys() == after.keys()
    assert all(before[key] == after[key] for key in before.keys() - changed)
    assert hashlib.sha256(source.read_bytes()).digest() == digest
    reopened = _complete_export(project, outputs)
    for asset in faces[:2]:
        assert reopened.asset(asset.key).original.tobytes() == asset.replacement.tobytes()


@pytest.mark.parametrize("mode", [FaceMode.AUTO, FaceMode.CUSTOM])
def test_resized_frames_roundtrip_without_stretching_other_faces(project, tmp_path, mode):
    project.options.face_mode = mode
    source = Image.new("RGBA", project.size, (30, 60, 90, 255))
    painting = project.paintings[1]
    face = next(a for a in project.assets if a.kind == Kind.FACE)
    untouched_face = next(a for a in project.assets if a.kind == Kind.FACE and a != face)
    if mode == FaceMode.CUSTOM:
        project.options.extensions[painting.key] = (-100, -50, 100, 50)
        painting.replacement, painting.replacement_box = prepare_replacement(project, painting, source)
    face.replacement, face.replacement_box = prepare_replacement(project, face, source)
    reopened = _complete_export(project, UnityWriter().export(project, tmp_path))
    assert reopened.face.box(reopened.bias) == face.replacement_box
    assert reopened.paintings[0].placement.box(reopened.bias) == project.paintings[0].placement.box(
        project.bias
    )
    if mode == FaceMode.CUSTOM:
        assert reopened.asset(painting.key).placement.box(reopened.bias) == painting.replacement_box
        assert reopened.asset(painting.key).raw_size == painting.replacement.size
    old_box = project.face.box(project.bias)
    box = face.replacement_box
    restored = reopened.asset(untouched_face.key).original.crop(
        (old_box[0] - box[0], old_box[1] - box[1], old_box[2] - box[0], old_box[3] - box[1])
    )
    assert restored.tobytes() == untouched_face.original.tobytes()


def test_psd_dimensions_and_face_group(project, tmp_path):
    path = export_psd(project, tmp_path / "layers.psd")
    psd = PSDImage.open(path)
    assert psd.size == project.size
    names = [layer.name for layer in psd.descendants()]
    assert "paintingface" in names
    assert any(name.startswith("face #") for name in names)


def test_root_crop_preserves_external_pivot_and_child_positions(project, tmp_path):
    project.options.face_mode = FaceMode.CUSTOM
    root = project.paintings[0]
    project.options.extensions[root.key] = (100, 50, -100, -50)
    root.replacement, root.replacement_box = prepare_replacement(
        project, root, Image.new("RGBA", project.size, (40, 60, 80, 255))
    )
    reopened = _complete_export(project, UnityWriter().export(project, tmp_path))
    old, new = root.placement, reopened.paintings[0].placement
    for i, shift in enumerate((100, 50)):
        assert new.size[i] * new.pivot[i] + shift == pytest.approx(old.size[i] * old.pivot[i], abs=0.001)
        assert reopened.face.origin[i] + shift == pytest.approx(project.face.origin[i], abs=0.001)
        assert reopened.paintings[1].placement.origin[i] + shift == pytest.approx(
            project.paintings[1].placement.origin[i], abs=0.001
        )


def test_resizing_parent_preserves_rotated_scaled_and_stretched_descendants(project):
    env = UnityPy.load(str(project.metadata))
    root_id = project.paintings[0].placement.rect.path_id
    child_id = project.paintings[1].placement.rect.path_id
    reader = next(r for r in env.objects if r.path_id == child_id)
    data = reader.parse_as_dict()
    data["m_LocalScale"].update(x=1.7, y=0.6)
    data["m_LocalRotation"].update(x=0, y=0, z=math.sin(math.pi / 8), w=math.cos(math.pi / 8))
    data["m_AnchorMin"].update(x=0.2, y=0.25)
    data["m_AnchorMax"].update(x=0.7, y=0.75)
    reader.patch(data)
    env = UnityPy.load(env.file.save())

    def nodes():
        found = {}

        def visit(transform, parent=None):
            node = transform_node(transform, parent)
            found[transform.object_reader.path_id] = node
            for pointer in transform.m_Children:
                visit(pointer.deref_parse_as_object(), node)

        visit(next(r for r in env.objects if r.path_id == root_id).parse_as_object())
        return found

    before = nodes()
    root = before[root_id].placement()
    target = root.reframe((100, 50, round(root.size[0]) - 80, round(root.size[1]) - 60), (0, 0))
    _resize_rects(env, {root_id: target})
    env = UnityPy.load(env.file.save())
    after = nodes()
    for key in before.keys() - {root_id}:
        old, new = before[key], after[key]
        assert new.local_size == pytest.approx(old.local_size, abs=0.002)
        for point in ((0, 0), (17, 0), (0, 23)):
            x, y = old.matrix.point(point)
            assert new.matrix.point(point) == pytest.approx((x - 100, y - 50), abs=0.003)


def test_cancelled_write_does_not_publish_partial_output(project, tmp_path):
    face = next(a for a in project.assets if a.kind == Kind.FACE)
    face.replacement = Image.new("RGBA", face.original.size, "red")

    def cancel(message, current, total):
        if str(message).startswith("Writing"):
            raise InterruptedError("cancel")

    with pytest.raises(InterruptedError):
        UnityWriter().export(project, tmp_path, cancel)
    assert list(tmp_path.iterdir()) == []


def test_psd_without_merged_preview_preserves_layer_transparency_and_position(tmp_path):
    image = Image.new("RGBA", (4, 3), (200, 40, 80, 128))
    asset = Asset(
        "body",
        "body",
        Kind.PAINTING,
        ObjectRef(Path("bundle"), "cab", 1),
        image,
        Placement((3, 2), image.size),
    )
    project = Project(Path("metadata"), "small", (30, 20), (0, 0), [asset])
    psd = PSDImage.open(export_psd(project, tmp_path / "small.psd"))
    assert not psd.image_resources.get_data(Resource.VERSION_INFO).has_composite
    assert all(not any(channel) for channel in psd._record.image_data.get_data(psd._record.header))
    preview = psd.composite(force=True, color=0, alpha=0)
    assert preview.mode == "RGBA"
    assert preview.getpixel((0, 0))[3] == 0
    assert preview.getpixel((3, 15))[3] == 128
    # A reader can rebuild the image from layers, including partial transparency.
    assert all(abs(a - b) <= 1 for a, b in zip(preview.getpixel((3, 15)), (200, 40, 80, 128)))
    assert psd[0].offset == (3, 15)
    assert psd[0].topil().tobytes() == upright(image).tobytes()
    assert psd._record.image_data.compression == Compression.RLE
    assert all(channel.compression == Compression.ZIP_WITH_PREDICTION for channel in psd[0]._channels)


@pytest.mark.parametrize(
    ("name", "mode", "painting_keys"),
    [
        ("u2501", FaceMode.OFF, ("u2501", "u2501_rw")),
        ("yunxian_2", FaceMode.AUTO, ("yunxian_2", "yunxian_2_bj", "yunxian_2_rw")),
        ("aijier_3", FaceMode.CUSTOM, ("aijier_3", "aijier_3_bj2", "aijier_3_bj1", "aijier_3_rw")),
    ],
    ids=["u2501-off", "yunxian-auto", "aijier-custom"],
)
def test_representative_projects_import_write_reopen_and_psd(name, mode, painting_keys, tmp_path):
    metadata = RESOURCES / name / name
    if not metadata.is_file():
        pytest.skip(f"本地真实资源 projects/{name} 不存在")
    project = UnityReader().load(metadata)
    assert tuple(asset.key for asset in project.paintings) == painting_keys
    bounds = [asset.placement.box(project.bias) for asset in project.paintings]
    bounds.append(project.face.box(project.bias))
    assert project.size == (max(box[2] for box in bounds), max(box[3] for box in bounds))
    project.options.face_mode = mode
    painting = project.preferred()
    face = next(asset for asset in project.assets if asset.kind == Kind.FACE)
    icon = next(asset for asset in project.assets if asset.kind == Kind.ICON)
    if mode == FaceMode.CUSTOM:
        extension = (-16, -8, 24, 16)
        project.options.extensions[painting.key] = extension
        project.options.extensions["paintingface"] = tuple(
            value + offset for value, offset in zip(project.options.extensions["paintingface"], extension)
        )

    # A real PNG boundary plus asymmetric pixels detects vertical flips and bad crops.
    source = Image.new("RGBA", project.size, (25, 60, 90, 255))
    left, bottom, right, top = painting.placement.box(project.bias)
    ImageDraw.Draw(source).rectangle(
        (left, bottom, (left + right) // 2, (bottom + top) // 2), fill=(200, 80, 40, 255)
    )
    imported_path = tmp_path / "import.png"
    upright(source).save(imported_path)
    source = read_image(imported_path)
    for asset in (painting, face, icon):
        asset.replacement, asset.replacement_box = prepare_replacement(project, asset, source)
    source.close()
    if mode != FaceMode.CUSTOM:
        assert painting.replacement.size == painting.raw_size

    reopened = _complete_export(project, UnityWriter().export(project, tmp_path / "exports"))
    for asset in (painting, face, icon):
        assert reopened.asset(asset.key).original.tobytes() == asset.replacement.tobytes()
    assert reopened.asset(painting.key).mesh_size == painting.replacement.size
    if mode != FaceMode.OFF:
        assert reopened.face.box(reopened.bias) == face.replacement_box
    for asset in project.paintings:
        expected = (
            asset.replacement_box
            if asset is painting and mode == FaceMode.CUSTOM
            else asset.placement.box(project.bias)
        )
        assert reopened.asset(asset.key).placement.box(reopened.bias) == expected
        if asset is not painting:
            assert reopened.asset(asset.key).original.tobytes() == asset.original.tobytes()

    psd = PSDImage.open(export_psd(project, tmp_path / "layers.psd"))
    assert psd.size == project.size
    assert [layer.name for layer in psd if not layer.is_group()] == [
        f"{asset.name} [{asset.texture_name}]" for asset in project.paintings
    ]
    for layer, asset in zip((layer for layer in psd if not layer.is_group()), project.paintings):
        image, box = display_layer(project, asset)
        assert layer.offset == (box[0], project.size[1] - box[1] - image.height)
        assert layer.topil().tobytes() == upright(image).tobytes()
    assert all(not layer.visible for layer in psd.find("paintingface"))
