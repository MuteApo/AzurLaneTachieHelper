"""Unity layout is resolved before local TRS; rasterization happens once."""

import math
from pathlib import Path
from types import SimpleNamespace as NS

import numpy as np
import pytest
from PIL import Image

from adapters.unity.transforms import transform_node
from domain.imaging import display_layer, prepare_replacement
from domain.model import Asset, FaceMode, Kind, ObjectRef, Placement, Project


def rect(size, *, pivot=(0.5, 0.5), anchor=(0.5, 0.5), stretch=None, position=(0, 0), scale=(1, 1), angle=0):
    q = math.radians(angle) / 2
    return NS(
        m_GameObject=NS(deref_parse_as_object=lambda: NS(m_Name="rect")),
        m_SizeDelta=NS(x=size[0], y=size[1]),
        m_Pivot=NS(x=pivot[0], y=pivot[1]),
        m_AnchorMin=NS(x=anchor[0], y=anchor[1]),
        m_AnchorMax=NS(x=(stretch or anchor)[0], y=(stretch or anchor)[1]),
        m_AnchoredPosition=NS(x=position[0], y=position[1]),
        m_LocalPosition=NS(x=0, y=0),
        m_LocalScale=NS(x=scale[0], y=scale[1]),
        m_LocalRotation=NS(x=0, y=0, z=math.sin(q), w=math.cos(q)),
    )


def test_stretch_anchors_use_unscaled_parent_rect_before_rotating_and_scaling():
    root = transform_node(rect((200, 100), pivot=(0.25, 0.75), scale=(0.4, 0.4)))
    # Child pivot is (135, 35); stretching contributes (100, 50) before its scale.
    child = transform_node(
        rect(
            (-20, 10),
            pivot=(0.75, 0.25),
            anchor=(0.25, 0.25),
            stretch=(0.75, 0.75),
            position=(10, -2.5),
            scale=(2, 0.5),
            angle=90,
        ),
        root,
    )
    assert child.local_size == pytest.approx((80, 60))
    assert child.pivot_position == pytest.approx((135, 35))
    # Bottom-left -> rotate (-120,-7.5) by 90 degrees, then translate by pivot.
    assert child.origin == pytest.approx((142.5, -85))
    assert child.placement().bounds() == pytest.approx((112.5, -85, 142.5, 75))
    # An additional rotation under non-uniform scale produces shear. Multiplying
    # scales/adding angles separately cannot reproduce this point.
    grandchild = transform_node(rect((10, 10), pivot=(0, 0), position=(0, 0), angle=90), child)
    assert grandchild.matrix.point((10, 0)) == pytest.approx((122.5, -5))
    assert grandchild.matrix.point((0, 10)) == pytest.approx((127.5, -25))


def test_rect_under_plain_transform_uses_local_position_not_anchors():
    root = transform_node(rect((100, 100)))
    plain = rect((0, 0), scale=(2, 3), angle=90)
    del plain.m_SizeDelta
    plain.m_LocalPosition = NS(x=10, y=20)
    parent = transform_node(plain, root)
    child = rect((4, 6), position=(900, 900), pivot=(0, 0))
    child.m_LocalPosition = NS(x=3, y=5)
    placed = transform_node(child, parent)
    assert placed.origin == pytest.approx((45, 76))


def project_with(image, placement, *, raw_size=None, mesh_image=None, preserve=False):
    asset = Asset(
        "body",
        "body",
        Kind.PAINTING,
        ObjectRef(Path("bundle"), "cab", 1),
        image,
        placement,
        raw_size=raw_size,
        mesh_image=mesh_image,
        preserve_aspect=preserve,
    )
    project = Project(Path("metadata"), "test", (40, 40), (0, 0), [asset])
    return project, asset


def test_mesh_coverage_keeps_original_transparent_margin_and_independent_xy_scale():
    tile = Image.new("RGBA", (2, 2), "red")
    project, asset = project_with(tile, Placement((0, 0), (12, 4)), raw_size=(6, 4), mesh_image=tile)
    image, box = display_layer(project, asset)
    assert box == (0, 0, 12, 4) and image.size == (12, 4)
    assert image.getpixel((1, 1)) == (255, 0, 0, 255)
    assert image.getpixel((9, 1))[3] == 0
    assert image.getpixel((1, 3))[3] == 0
    assert asset.decoded().size == (6, 4)


@pytest.mark.parametrize(
    "axes,origin,expected",
    [
        (((0, 1), (-1, 0)), (6, 2), Image.Transpose.ROTATE_270),
        (((-1, 0), (0, 1)), (6, 2), Image.Transpose.FLIP_LEFT_RIGHT),
    ],
)
def test_rotated_and_mirrored_import_is_inverse_of_display(axes, origin, expected):
    pixels = np.arange(3 * 2 * 4, dtype=np.uint8).reshape((2, 3, 4))
    pixels[:, :, 3] = 255
    original = Image.fromarray(pixels)
    project, asset = project_with(original, Placement(origin, (3, 2), axes=axes), raw_size=(3, 2))
    image, box = display_layer(project, asset)
    assert image.tobytes() == original.transpose(expected).tobytes()
    canvas = Image.new("RGBA", project.size)
    canvas.paste(image, box[:2])
    restored, _ = prepare_replacement(project, asset, canvas)
    assert restored.tobytes() == original.tobytes()


def test_preserve_aspect_uses_pivot_and_local_size_before_nonuniform_scale():
    # Local rect is 8x8, with 2x horizontal scale. A 4x2 sprite occupies local
    # 8x4 at the top edge (pivot.y=1), then becomes 16x4 in prefab coordinates.
    project, asset = project_with(
        Image.new("RGBA", (4, 2), "red"),
        Placement((0, 0), (16, 8), pivot=(0, 1), scale=(2, 1)),
        preserve=True,
    )
    image, box = display_layer(project, asset)
    assert image.size == (16, 4) and box == (0, 4, 16, 8)


def test_expanding_fractional_rect_retains_untouched_pixel_grid():
    placement = Placement((10.4, 20.6), (4, 6))
    expanded = placement.reframe((8, 18, 18, 30), (0, 0))
    assert expanded.origin == pytest.approx((8.4, 17.6))
    assert expanded.size == (10, 12)
    assert expanded.box() == (8, 18, 18, 30)


def test_custom_zero_extension_retains_rotated_geometry_and_local_aspect():
    angle = math.sqrt(0.5)
    rotated = Placement((10, 10), (8, 8), axes=((angle, angle), (-angle, angle)))
    project, asset = project_with(Image.new("RGBA", (8, 8), "red"), rotated, raw_size=(8, 8))
    project.options.face_mode = FaceMode.CUSTOM
    asset.replacement, asset.replacement_box = prepare_replacement(
        project, asset, Image.new("RGBA", project.size, "blue")
    )
    assert display_layer(project, asset)[1] == rotated.box()
    assert asset.replacement.size == (8, 8)

    project, asset = project_with(
        Image.new("RGBA", (8, 8), "red"),
        Placement((0, 0), (16, 8), scale=(2, 1)),
        raw_size=(8, 8),
        preserve=True,
    )
    project.options.face_mode = FaceMode.CUSTOM
    asset.replacement, asset.replacement_box = prepare_replacement(
        project, asset, Image.new("RGBA", project.size, "blue")
    )
    assert asset.replacement.size == (8, 8)
    assert display_layer(project, asset)[1] == (0, 0, 16, 8)
