from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from domain.imaging import (
    clip_icon,
    decode_mesh,
    prepare_replacement,
    read_image,
    replacement_bounds,
    upright,
)
from domain.model import Asset, FaceMode, IconPreset, Kind, ObjectRef, Placement, Project


def test_file_orientation_and_icon_sampling(tmp_path):
    pixels = np.zeros((8, 8, 4), dtype=np.uint8)
    pixels[:, :, 3] = 255
    pixels[:4, :, 0] = 255
    pixels[4:, :, 2] = 255
    source = Image.fromarray(pixels)
    path = tmp_path / "asymmetric.png"
    source.save(path)
    internal = read_image(path)
    assert upright(internal).tobytes() == source.tobytes()
    clipped = clip_icon(internal, (4, 4), IconPreset((4, 4), (0.5, 0.5), 1))
    assert clipped.tobytes() == internal.crop((2, 2, 6, 6)).tobytes()


def test_mesh_winding_and_rotated_uv():
    pixels = np.arange(4 * 4 * 4, dtype=np.uint8).reshape((4, 4, 4))
    pixels[:, :, 3] = 255
    texture = Image.fromarray(pixels)
    vertices = [(0, 0), (0, 4), (4, 4), (4, 0)]
    uv = [(0, 0), (0, 1), (1, 1), (1, 0)]
    decoded = decode_mesh(texture, vertices, uv, [2, 1, 0, 0, 3, 2])
    assert decoded.tobytes() == texture.tobytes()
    rotated = decode_mesh(texture, vertices, uv[1:] + uv[:1], [0, 1, 2, 2, 3, 0])
    assert rotated.tobytes() == texture.transpose(Image.Transpose.ROTATE_270).tobytes()


@pytest.mark.parametrize("shadow", [False, True])
def test_cached_portrait_source_matches_export_including_transparency(shadow):
    pixels = np.random.default_rng(7).integers(0, 256, (180, 240, 4), dtype=np.uint8)
    source = Image.fromarray(pixels)
    preset = IconPreset((96, 128), (0.43, 0.67), 0.8, 27)
    expected = clip_icon(source, (120, 90), preset, shadow)
    cached = clip_icon(source.convert("RGBa"), (120, 90), preset, shadow)
    assert cached.mode == "RGBA"
    assert cached.tobytes() == expected.tobytes()


def test_face_modes_preserve_off_frame_and_clip_expanded_frame():
    ref = ObjectRef(Path("bundle"), "cabinet", 1)
    painting = Asset("body", "body", Kind.PAINTING, ref, Image.new("RGBA", (8, 8)), Placement((0, 0), (8, 8)))
    face = Asset("face/0", "0", Kind.FACE, ref, Image.new("RGBA", (4, 4)))
    project = Project(Path("meta"), "test", (8, 8), (0, 0), [painting, face], Placement((6, 6), (4, 4)))
    source = Image.new("RGBA", (8, 8), "red")
    assert replacement_bounds(project, face) == (6, 6, 10, 10)
    result, box = prepare_replacement(project, face, source)
    assert result.size == (4, 4) and box == (6, 6, 10, 10)
    assert result.getpixel((3, 3))[3] == 0
    project.options.face_mode = FaceMode.AUTO
    assert replacement_bounds(project, face) == (0, 0, 8, 8)
    assert prepare_replacement(project, face, source)[1] == (0, 0, 8, 8)
    project.options.face_mode = FaceMode.CUSTOM
    project.options.extensions["paintingface"] = (-2, -2, 0, 0)
    # The preview retains the requested rectangle; only the imported pixels are clipped.
    assert replacement_bounds(project, face) == (4, 4, 10, 10)
    assert prepare_replacement(project, face, source)[1] == (4, 4, 8, 8)
    project.options.extensions["paintingface"] = (20, 20, 30, 30)
    with pytest.raises(ValueError, match="does not overlap"):
        prepare_replacement(project, face, source)
