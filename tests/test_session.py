import json
from pathlib import Path

import pytest
from PIL import Image, UnidentifiedImageError

from application.session import MissingSourceError, Session
from domain.imaging import prepare_replacement
from domain.model import Asset, FaceMode, IconPreset, Kind, ObjectRef, Placement, Project


@pytest.fixture
def project_factory(tmp_path, monkeypatch):
    metadata = tmp_path / "resources" / "ship"
    metadata.parent.mkdir()
    metadata.write_bytes(b"mocked Unity metadata")
    monkeypatch.setattr("application.session.discover_manifest", lambda path: None)

    def make():
        def reference(number):
            return ObjectRef(metadata, "cabinet", number)

        return Project(
            metadata,
            "ship",
            (8, 8),
            (0, 0),
            [
                Asset(
                    "painting/ship",
                    "ship",
                    Kind.PAINTING,
                    reference(1),
                    Image.new("RGBA", (8, 8), "blue"),
                    Placement((0, 0), (8, 8)),
                ),
                Asset("paintingface/1", "1", Kind.FACE, reference(2), Image.new("RGBA", (2, 2), "yellow")),
                Asset(
                    "squareicon", "squareicon", Kind.ICON, reference(3), Image.new("RGBA", (4, 4), "black")
                ),
            ],
            face=Placement((2, 3), (2, 2)),
        )

    return make


def write_image(path: Path, color: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (8, 8), color).save(path)
    return path


def test_failed_batch_import_preserves_edits_and_history(project_factory, tmp_path):
    session = Session(project_factory())
    first = write_image(tmp_path / "first.png", "red")
    session.import_images({"painting/ship": first})
    before = session.preview("painting/ship").tobytes()
    revision = session.revision
    next_image = write_image(tmp_path / "second.png", "green")
    invalid = tmp_path / "broken.png"
    invalid.write_bytes(b"not a picture")

    with pytest.raises(UnidentifiedImageError):
        session.import_images({"painting/ship": next_image, "paintingface/1": invalid})

    assert session.preview("painting/ship").tobytes() == before
    assert session.sources == {"painting/ship": first.resolve()}
    assert session.revision == revision
    assert str(session.undo_label) == "import 1 images"
    session.undo()
    assert not session.dirty
    assert not session.project.modified


def test_invalid_custom_crop_does_not_commit_options(project_factory, tmp_path):
    session = Session(project_factory())
    session.import_images({"paintingface/1": write_image(tmp_path / "face.png", "red")})
    revision = session.revision
    before = session.preview("paintingface/1").tobytes()

    with pytest.raises(ValueError, match="does not overlap"):
        session.set_options(face_mode=FaceMode.CUSTOM, extensions={"paintingface": (100, 100, 100, 100)})

    assert session.project.options.face_mode == FaceMode.OFF
    assert session.project.options.extensions == {}
    assert session.revision == revision
    assert session.preview("paintingface/1").tobytes() == before


def test_save_reopen_relative_sources_and_independent_export_state(project_factory, tmp_path, monkeypatch):
    session = Session(project_factory())
    source = write_image(tmp_path / "edits" / "ship.png", "red")
    session.import_images({"painting/ship": source})
    assert session.dirty and session.export_dirty
    document_path = session.save(tmp_path / "editing.tachie.json")
    document = json.loads(document_path.read_text(encoding="utf-8"))
    assert document["metadata"] == "resources/ship"
    saved_source = tmp_path / document["sources"]["painting/ship"]
    assert saved_source.parent == tmp_path / "editing.tachie.assets"
    assert saved_source.read_bytes() == source.read_bytes()
    assert not session.dirty and session.export_dirty
    session.mark_exported()
    assert not session.export_dirty
    session.undo()
    assert session.dirty and session.can_redo
    session.redo()
    assert not session.dirty and not session.export_dirty

    monkeypatch.setattr("application.session.UnityReader.load", lambda *args: project_factory())
    # Version 1 documents may still carry the retired reconstruction switch.
    document["options"]["mesh_mode"] = True
    document_path.write_text(json.dumps(document), encoding="utf-8")
    progress = []

    def prepare(*args):
        # Decoding saved replacements must not leave the bar at resource-load completion.
        assert progress[-1] == ("Restoring edits…", 0, 0)
        return prepare_replacement(*args)

    monkeypatch.setattr("application.session.prepare_replacement", prepare)
    restored = Session.open(
        document_path,
        progress=lambda message, current, total: progress.append((str(message), current, total)),
    )
    assert not restored.dirty
    assert restored.export_dirty
    assert restored.sources == {"painting/ship": saved_source}
    assert restored.preview("painting/ship").tobytes() == session.preview("painting/ship").tobytes()
    restored.save(document_path)
    assert "mesh_mode" not in json.loads(document_path.read_text(encoding="utf-8"))["options"]


def test_clipped_files_use_preset_sizes_and_are_one_undo_step(project_factory, tmp_path):
    session = Session(project_factory())
    source = write_image(tmp_path / "reference.png", "red")
    presets = {"squareicon": IconPreset((4, 4), scale=1), "herohrzicon": IconPreset((6, 2), scale=1)}
    files = session.clip_icons(source, presets, tmp_path / "outputs")
    for path in files:
        with Image.open(path) as image:
            assert image.size == presets[path.stem].size
    assert session.project.asset("squareicon").modified
    assert str(session.undo_label) == "crop portraits"
    session.undo()
    assert not session.project.modified
    assert not session.dirty
    session.redo()
    assert session.project.asset("squareicon").modified


def test_invalid_clip_preserves_state_and_creates_no_outputs(project_factory, tmp_path):
    session = Session(project_factory())
    source = write_image(tmp_path / "reference.png", "red")
    with pytest.raises(ValueError, match="Scale"):
        session.clip_icons(source, {"squareicon": IconPreset((4, 4), scale=0)}, tmp_path / "outputs")
    assert not session.dirty
    assert not session.can_undo
    assert not (tmp_path / "outputs").exists()


def test_portraits_apply_without_export_and_survive_saved_project(project_factory, tmp_path, monkeypatch):
    session = Session(project_factory())
    source = write_image(tmp_path / "reference.png", "red")
    existing = set(tmp_path.iterdir())
    presets = {"squareicon": IconPreset((4, 4), scale=1)}
    assert session.clip_icons(source, presets) == []
    assert set(tmp_path.iterdir()) == existing
    expected = session.project.asset("squareicon").replacement.tobytes()
    session.undo()
    assert not session.project.modified
    session.redo()
    assert session.project.asset("squareicon").replacement.tobytes() == expected
    saved = session.save(tmp_path / "editing.tachie.json")
    session.close()
    monkeypatch.setattr("application.session.UnityReader.load", lambda *args: project_factory())
    reopened = Session.open(saved)
    assert reopened.project.asset("squareicon").replacement.tobytes() == expected
    reopened.close()


def test_reopen_can_relocate_missing_metadata_and_replacement(project_factory, tmp_path, monkeypatch):
    session = Session(project_factory())
    source = write_image(tmp_path / "old.png", "red")
    session.import_images({"painting/ship": source})
    saved = session.save(tmp_path / "editing.tachie.json")
    saved_source = tmp_path / json.loads(saved.read_text(encoding="utf-8"))["sources"]["painting/ship"]
    original_metadata = session.project.metadata
    moved_metadata = original_metadata.rename(tmp_path / "moved-metadata")
    moved_image = saved_source.rename(tmp_path / "moved-image.png")

    def load(self, metadata, *args):
        project = project_factory()
        project.metadata = metadata
        return project

    monkeypatch.setattr("application.session.UnityReader.load", load)

    with pytest.raises(MissingSourceError) as missing:
        Session.open(saved)
    assert missing.value.path == original_metadata
    with pytest.raises(MissingSourceError) as missing:
        Session.open(saved, relocations={str(original_metadata): moved_metadata})
    assert missing.value.path == saved_source
    restored = Session.open(
        saved, relocations={str(original_metadata): moved_metadata, str(saved_source): moved_image}
    )
    assert restored.sources == {"painting/ship": moved_image}
    assert restored.project.metadata == moved_metadata
    assert restored.preview("painting/ship").getpixel((0, 0)) == (255, 0, 0, 255)
    assert restored.dirty
    restored.save(saved)
    assert not restored.dirty
    document = json.loads(saved.read_text(encoding="utf-8"))
    assert document["metadata"] == "moved-metadata"
    assert tmp_path / document["sources"]["painting/ship"] == saved_source
    assert saved_source.read_bytes() == moved_image.read_bytes()


def test_reimport_overwritten_file_and_undo_keep_exact_pixels(project_factory, tmp_path):
    session = Session(project_factory())
    source = write_image(tmp_path / "ship.png", "red")
    session.import_images({"painting/ship": source})
    write_image(source, "green")
    session.import_images({"painting/ship": source})
    assert session.preview("painting/ship").getpixel((0, 0)) == (0, 128, 0, 255)
    source.unlink()
    session.undo()
    assert session.preview("painting/ship").getpixel((0, 0)) == (255, 0, 0, 255)
    session.redo()
    assert session.preview("painting/ship").getpixel((0, 0)) == (0, 128, 0, 255)
    replacement = session.project.asset("painting/ship").replacement
    session.set_options(compression="lz4")
    session.set_presets({"squareicon": IconPreset((4, 4), scale=0.7)})
    assert session.project.asset("painting/ship").replacement is replacement


def test_saved_edits_survive_original_overwrite_and_deletion(project_factory, tmp_path, monkeypatch):
    session = Session(project_factory())
    source = write_image(tmp_path / "ship.png", "red")
    session.import_images({"painting/ship": source})
    write_image(source, "green")
    document = session.save(tmp_path / "project.json")
    source.unlink()
    session.save(document)
    assert len(list((tmp_path / "project.assets").iterdir())) == 1
    session.close()

    monkeypatch.setattr("application.session.UnityReader.load", lambda *args: project_factory())
    restored = Session.open(document)
    assert restored.preview("painting/ship").getpixel((0, 0)) == (255, 0, 0, 255)
    assert not restored.dirty
    restored.close()


def test_match_psd_layer_and_texture_names_preserves_ambiguity(project_factory):
    session = Session(project_factory())
    session.project.asset("painting/ship").texture_name = "ship_tex"
    session.project.asset("squareicon").texture_name = "ship_tex"
    paths = [Path("ship [ship_tex].png"), Path("ship_tex.png"), Path("face #1.png")]
    assert session.match_images(paths) == {
        paths[0]: ["painting/ship"],
        paths[1]: ["painting/ship", "squareicon"],
        paths[2]: ["paintingface/1"],
    }
