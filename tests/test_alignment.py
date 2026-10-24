"""Canvas mismatch interaction and the resulting persistent, pixel-exact import."""

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from adapters.storage import Settings
from application.session import Session
from domain.imaging import align_image, upright
from domain.model import Asset, ImageAlignment, Kind, ObjectRef, Placement, Project
from ui.dialogs.alignment import AlignmentDialog
from ui.studio.window import MainWindow


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def project_factory(tmp_path, monkeypatch):
    metadata = tmp_path / "ship"
    metadata.write_bytes(b"synthetic metadata")
    monkeypatch.setattr("application.session.discover_manifest", lambda path: None)

    def make():
        return Project(
            metadata,
            "Ship",
            (80, 60),
            (0, 0),
            [
                Asset(
                    "body",
                    "Body",
                    Kind.PAINTING,
                    ObjectRef(metadata, "cab", 1),
                    Image.new("RGBA", (80, 60), "blue"),
                    Placement((0, 0), (80, 60)),
                ),
                *[
                    Asset(
                        f"face/{i}",
                        str(i),
                        Kind.FACE,
                        ObjectRef(metadata, "cab", i + 2),
                        Image.new("RGBA", (8, 8)),
                    )
                    for i in range(2)
                ],
            ],
            face=Placement((30, 36), (8, 8)),
        )

    monkeypatch.setattr("application.session.UnityReader.load", lambda *args: make())
    return make


def imports(tmp_path):
    result = {}
    for i, color in enumerate(("red", "yellow")):
        image = Image.new("RGBA", (40, 30))
        image.paste(color, (10, 6, 18, 14))
        path = tmp_path / f"{i}.png"
        image.save(path)
        result[f"face/{i}"] = path
    return result


def test_alignment_padding_scaling_and_clipping():
    source = Image.new("RGBA", (2, 2))
    source.putpixel((0, 0), (250, 20, 30, 128))
    source.putpixel((1, 1), (20, 240, 40, 255))
    placed = upright(align_image(upright(source), (8, 6), ImageAlignment(3, 1)))
    assert placed.crop((3, 1, 5, 3)).tobytes() == source.tobytes()
    assert placed.getbbox() == (3, 1, 5, 3)
    clipped = upright(align_image(upright(source), (2, 2), ImageAlignment(-1, -1)))
    assert clipped.getpixel((0, 0)) == source.getpixel((1, 1))
    solid = Image.new("RGBA", (2, 2), (100, 150, 200, 255))
    enlarged = upright(align_image(solid, (8, 8), ImageAlignment(2, 2, 2)))
    assert enlarged.getbbox() == (2, 2, 6, 6)
    assert enlarged.getpixel((3, 3)) == (100, 150, 200, 255)


def test_aligned_batch_uses_snapshots_undo_and_portable_save(project_factory, tmp_path):
    session = Session(project_factory())
    paths = imports(tmp_path)
    prepared = session.prepare_imports(paths)
    assert not session.dirty and not session.can_undo
    # External edits during the dialog must not replace the image the user aligned.
    Image.new("RGBA", (40, 30), "green").save(paths["face/0"])
    session.import_prepared(prepared, {key: ImageAlignment(20, 10) for key in paths})
    assert session.preview("face/0").getpixel((0, 0)) == (255, 0, 0, 255)
    assert session.preview("face/1").getpixel((0, 0)) == (255, 255, 0, 255)
    assert (
        session.preview("face/0", composite=True).tobytes()
        != session.preview("face/1", composite=True).tobytes()
    )
    session.undo()
    assert not session.project.modified
    session.redo()
    saved = session.save(tmp_path / "saved.tachie.json")
    expected = session.preview("face/0").tobytes()
    session.close()
    restored = Session.open(saved)
    assert restored.preview("face/0").tobytes() == expected
    assert all(Image.open(path).size == (80, 60) for path in restored.sources.values())
    restored.close()


def test_dialog_drags_nudges_shares_and_rejects_empty_placement(app, project_factory, tmp_path):
    session = Session(project_factory())
    items = session.prepare_imports(imports(tmp_path))
    dialog = AlignmentDialog(items)
    dialog.show()
    app.processEvents()
    start = dialog.view.mapFromScene(35, 25)
    end = start + QPoint(30, 20)
    QTest.mousePress(dialog.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(dialog.view.viewport(), end)
    QTest.mouseRelease(dialog.view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    after_drag = dialog.alignments[items[0].key]
    assert after_drag.x > 20 and after_drag.y > 15
    QTest.keyClick(dialog.view, Qt.Key.Key_Left)
    assert dialog.alignments[items[0].key].x == after_drag.x - 1
    assert dialog.alignments[items[0].key] == dialog.alignments[items[1].key]
    dialog.files.setCurrentIndex(1)
    assert dialog.offset_x.value() == after_drag.x - 1
    dialog.shared.setChecked(False)
    dialog.offset_x.setValue(1000)
    assert not dialog.apply_button.isEnabled()
    assert dialog.alignments[items[0].key].x != 1000
    dialog._reset()
    assert dialog.apply_button.isEnabled()
    dialog.reject()
    assert not session.dirty
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    session.close()


def finish(app, window):
    deadline = time.monotonic() + 10
    while window.tasks.busy and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    assert not window.tasks.busy
    app.processEvents()


@pytest.mark.parametrize("mode", ["matched", "cancel", "align"])
def test_window_import_prompts_only_for_mismatch_and_cancels_entire_batch(
    app, project_factory, tmp_path, monkeypatch, mode
):
    session = Session(project_factory())
    window = MainWindow(Settings(tmp_path / "settings.json"))
    window._opened(session)
    finish(app, window)
    paths = imports(tmp_path)
    if mode == "matched":
        for path in paths.values():
            Image.new("RGBA", (80, 60), "red").save(path)
    body = tmp_path / "body.png"
    Image.new("RGBA", (80, 60), "cyan").save(body)
    paths["body"] = body
    calls = []

    def interact(dialog):
        calls.append(dialog)
        assert len(dialog.items) == 2
        dialog.offset_x.setValue(20)
        dialog.offset_y.setValue(10)
        return QDialog.DialogCode.Rejected if mode == "cancel" else QDialog.DialogCode.Accepted

    monkeypatch.setattr(AlignmentDialog, "exec", interact)
    window._import_mapping(paths, "Imported")
    finish(app, window)
    assert len(calls) == (0 if mode == "matched" else 1)
    assert len(session.project.modified) == (0 if mode == "cancel" else 3)
    if mode == "align":
        assert session.preview("face/0").getpixel((0, 0)) == (255, 0, 0, 255)
    if session.can_undo:
        session.undo()
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    session.close()
