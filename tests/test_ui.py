"""Exercise the Qt/application boundary without a display or real source assets."""

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from adapters.storage import Settings
from application.session import Session
from domain.imaging import clip_icon
from domain.messages import Message
from domain.model import Asset, FaceMode, IconPreset, Kind, ObjectRef, Placement, Project, default_presets
from ui.dialogs.portrait import CropDialog
from ui.studio.window import MainWindow
from ui.tasks import TaskRunner
from ui.widgets.canvas import Canvas


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def finish(app, runner):
    deadline = time.monotonic() + 10
    while runner.busy and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    assert not runner.busy, "Qt task did not finish"
    app.processEvents()


def test_edit_and_undo_update_window_on_main_thread(app, tmp_path):
    metadata = tmp_path / "sample"
    metadata.write_bytes(b"synthetic")
    original = Image.new("RGBA", (40, 60), "red")
    asset = Asset(
        "painting",
        "立绘",
        Kind.PAINTING,
        ObjectRef(metadata, "cab", 1),
        original,
        Placement((0, 0), (40, 60)),
        raw_size=(40, 60),
    )
    session = Session(Project(metadata, "Sample", (40, 60), (0, 0), [asset]))
    window = MainWindow(Settings(tmp_path / "settings.json"))
    window.show()
    window._opened(session)
    finish(app, window.tasks)
    assert window.sidebar.model.item(0).icon().pixmap(100, 100).toImage().pixelColor(10, 10).red() == 255
    replacement = tmp_path / "replacement.png"
    Image.new("RGBA", (40, 60), "blue").save(replacement)
    window._edit(lambda: session.import_images({asset.key: replacement}), "Imported")
    finish(app, window.tasks)
    assert session.dirty
    assert window.undo_action.isEnabled()
    assert "●" in window.windowTitle()
    assert window.preview.canvas.item.pixmap().toImage().pixelColor(10, 10).blue() == 255
    assert window.sidebar.model.item(0).icon().pixmap(100, 100).toImage().pixelColor(10, 10).blue() == 255
    window.undo()
    finish(app, window.tasks)
    assert not session.dirty
    assert window.preview.canvas.item.pixmap().toImage().pixelColor(10, 10).red() == 255
    assert window.sidebar.model.item(0).icon().pixmap(100, 100).toImage().pixelColor(10, 10).red() == 255
    window.close()


def test_asset_filters_preserve_edit_target_and_theme_preserves_preview(app, tmp_path):
    from PySide6.QtCore import QCoreApplication, Qt

    source = tmp_path / "sample"
    assets = [
        Asset(
            "main",
            "Main",
            Kind.PAINTING,
            ObjectRef(source, "cab", 1),
            Image.new("RGBA", (40, 60), "red"),
            Placement((0, 0), (40, 60)),
        ),
        Asset("face", "Smile", Kind.FACE, ObjectRef(source, "cab", 2), Image.new("RGBA", (10, 10), "blue")),
    ]
    session = Session(Project(source, "Sample", (40, 60), (0, 0), assets, face=Placement((0, 0), (10, 10))))
    window = MainWindow(Settings(tmp_path / "settings.json"))
    window.show()
    window._opened(session)
    finish(app, window.tasks)
    window.sidebar.asset_filter.setCurrentIndex(2)
    assert window.sidebar.proxy.rowCount() == 1
    assert window.selected_key == "main"
    window.sidebar.tree.setCurrentIndex(window.sidebar.proxy.index(0, 0))
    finish(app, window.tasks)
    assert window.selected_key == "face"
    assert window.preview.canvas.item.pixmap().toImage().pixelColor(5, 5).blue() == 255
    window.sidebar.search.setText("MAIN")
    assert window.sidebar.proxy.rowCount() == 0
    assert window.selected_key == "face"
    window._refresh()
    assert window.sidebar.asset_summary.text() == QCoreApplication.translate("Window", "No matching images")
    window.sidebar.search.clear()
    assert window.sidebar.tree.currentIndex().data(Qt.ItemDataRole.UserRole) == "face"
    cached = window.preview.canvas.item.pixmap().cacheKey()
    window._set_theme(Qt.ColorScheme.Dark)
    window._set_theme(Qt.ColorScheme.Light)
    assert window.preview.canvas.item.pixmap().cacheKey() == cached
    assert not window.tasks.busy
    window.close()


def test_worker_failure_releases_busy_state_and_exposes_details(app):
    from PySide6.QtCore import QObject

    parent = QObject()
    runner = TaskRunner(parent)
    failures = []
    updates = []
    runner.failed.connect(lambda error, details: failures.append((error, details)))
    runner.progress.connect(lambda message, current, total: updates.append(message))
    message = Message("Reading {0}", ("resource {name}",))

    def operation(progress):
        progress(message, 0, 1)
        raise ValueError("missing layer")

    runner.start(operation, lambda result: pytest.fail("failed operation reported success"))
    finish(app, runner)
    assert updates[-1] is message
    assert len(failures) == 1
    assert isinstance(failures[0][0], ValueError)
    assert "missing layer" in failures[0][1]


def test_icons_and_single_expressions_open_at_actual_size_including_cache_hits(app, tmp_path):
    from PySide6.QtCore import Qt

    session = small_session(tmp_path)
    project = session.project
    project.face = Placement((0, 0), (8, 8))
    for key, kind in (("face", Kind.FACE), ("icon", Kind.ICON)):
        project.assets.append(
            Asset(
                key,
                key,
                kind,
                ObjectRef(project.metadata, "cab", len(project.assets)),
                Image.new("RGBA", (8, 8), "blue"),
            )
        )
    window = MainWindow(Settings(tmp_path / "settings.json"))
    window.show()
    window._opened(session)
    finish(app, window.tasks)

    def select(key):
        item = next(
            window.sidebar.model.item(i)
            for i in range(window.sidebar.model.rowCount())
            if window.sidebar.model.item(i).data(Qt.ItemDataRole.UserRole) == key
        )
        window.sidebar.tree.setCurrentIndex(window.sidebar.proxy.mapFromSource(item.index()))
        finish(app, window.tasks)

    for key in ("face", "icon", "face"):
        select(key)
        assert window.preview.canvas.transform().m11() == pytest.approx(1)
        assert not window.preview.canvas._fit
    window.preview.canvas.zoom_by(2)
    window._request_preview()
    assert not window.tasks.busy  # Cached refresh retains a user's zoom.
    assert window.preview.canvas.transform().m11() == pytest.approx(2)
    window.preview.preview_mode.setCurrentIndex(1)
    finish(app, window.tasks)
    assert window.preview.canvas._fit  # Even when the composite has the same dimensions.
    select("icon")
    assert window.preview.canvas.transform().m11() == pytest.approx(1)
    select("face")
    assert window.preview.canvas._fit
    window.preview.preview_mode.setCurrentIndex(0)
    finish(app, window.tasks)
    assert window.preview.canvas.transform().m11() == pytest.approx(1)
    window.close()


@pytest.mark.parametrize("mode", [FaceMode.AUTO, FaceMode.CUSTOM])
def test_replacing_expanded_expression_fits_preview_and_preserves_manual_zoom_on_refresh(
    app, tmp_path, monkeypatch, mode
):
    from PySide6.QtWidgets import QFileDialog

    session = small_session(tmp_path)
    project = session.project
    project.face = Placement((0, 0), project.size)
    project.options.face_mode = mode
    project.assets.append(
        Asset("face", "Face", Kind.FACE, ObjectRef(project.metadata, "cab", 2), Image.new("RGBA", (8, 8)))
    )
    session = Session(project)
    replacement = tmp_path / "face.png"
    Image.new("RGBA", project.size, "blue").save(replacement)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(replacement), ""))
    window = MainWindow(Settings(tmp_path / "settings.json"))
    monkeypatch.setattr(window, "_confirm_discard", lambda *args: True)
    window.show()
    try:
        window._opened(session)
        finish(app, window.tasks)
        window.selected_key = "face"
        window._refresh()
        finish(app, window.tasks)
        assert window.preview.canvas.transform().m11() == pytest.approx(1)
        window.replace_selected()
        finish(app, window.tasks)
        assert window.preview.canvas._fit

        window.selected_key = "body"
        window._request_preview()
        finish(app, window.tasks)
        window.selected_key = "face"
        window._request_preview()
        assert not window.tasks.busy  # Cached expanded face also uses fit.
        assert window.preview.canvas._fit

        window.preview.canvas.actual_size()
        window.preview.canvas.zoom_by(2)
        manual_zoom = window.preview.canvas.transform().m11()
        window._request_preview()
        assert window.preview.canvas.transform().m11() == pytest.approx(manual_zoom)
        assert not window.preview.canvas._fit
        # Same-sized replacement must refit even after manually zooming in.
        Image.new("RGBA", project.size, "green").save(replacement)
        window.replace_selected()
        finish(app, window.tasks)
        assert window.preview.canvas._fit
    finally:
        window.close()


def test_preview_accepts_file_drop_and_clears_highlight(app, tmp_path, monkeypatch):
    from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
    from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent

    window = MainWindow(Settings(tmp_path / "settings.json"))
    window.show()
    window._opened(small_session(tmp_path))
    finish(app, window.tasks)
    received = []
    monkeypatch.setattr(window, "import_images", received.append)
    path = tmp_path / "replacement.png"
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path))])
    actions = Qt.DropAction.CopyAction
    buttons = Qt.MouseButton.LeftButton
    modifiers = Qt.KeyboardModifier.NoModifier
    viewport = window.preview.canvas.viewport()
    enter = QDragEnterEvent(QPointF(40, 40), actions, mime, buttons, modifiers)
    QApplication.sendEvent(viewport, enter)
    assert enter.isAccepted() and window.preview.canvas._drop_active
    move = QDragMoveEvent(QPointF(60, 60), actions, mime, buttons, modifiers)
    QApplication.sendEvent(viewport, move)
    assert move.isAccepted()
    QApplication.sendEvent(viewport, QDragLeaveEvent())
    assert not window.preview.canvas._drop_active
    enter = QDragEnterEvent(QPointF(40, 40), actions, mime, buttons, modifiers)
    QApplication.sendEvent(viewport, enter)
    drop = QDropEvent(QPointF(60, 60), actions, mime, buttons, modifiers)
    QApplication.sendEvent(viewport, drop)
    assert drop.isAccepted() and received == [[path]]
    assert not window.preview.canvas._drop_active
    window.tasks.busy = True
    window._update_state()
    enter = QDragEnterEvent(QPointF(40, 40), actions, mime, buttons, modifiers)
    QApplication.sendEvent(viewport, enter)
    assert not enter.isAccepted() and not window.preview.canvas._drop_active
    window.tasks.busy = False
    window.close()


@pytest.mark.parametrize("replaced", [False, True])
def test_custom_bounds_step_updates_preview_without_leaving_field(app, tmp_path, monkeypatch, replaced):
    project = small_session(tmp_path).project
    project.size = (128, 128)
    project.face = Placement((32, 32), (32, 32))
    project.options.face_mode = FaceMode.CUSTOM
    face = Asset(
        "face", "Face", Kind.FACE, ObjectRef(project.metadata, "cab", 2), Image.new("RGBA", (32, 32), "blue")
    )
    project.assets.append(face)
    session = Session(project)
    if replaced:
        path = tmp_path / "replacement.png"
        Image.new("RGBA", project.size, "green").save(path)
        session.import_images({"face": path})
    window = MainWindow(Settings(tmp_path / "settings.json"))
    monkeypatch.setattr(window, "_confirm_discard", lambda *args: True)
    window.show()
    try:
        window._opened(session)
        finish(app, window.tasks)
        window.selected_key = "face"
        window._refresh()
        finish(app, window.tasks)
        assert window.preview.preview_mode.currentData() is False
        window.inspector.extensions[0].stepUp()
        finish(app, window.tasks)
        assert project.options.extensions["paintingface"] == (25, 0, 0, 0)
        assert window.preview.preview_mode.currentData() is True
        assert window.preview.canvas.boundary.isVisible()
        rect = window.preview.canvas.boundary.rect()
        assert (rect.left(), rect.top(), rect.width(), rect.height()) == (57, 64, 7, 32)
        if replaced:
            assert face.replacement.size == (7, 32)
        window.inspector.extensions[0].setValue(3)  # Direct entry still allows single-pixel precision.
        finish(app, window.tasks)
        assert window.preview.canvas.boundary.rect().left() == 35
    finally:
        window.close()


def small_session(tmp_path):
    metadata = tmp_path / "sample"
    metadata.write_bytes(b"synthetic")
    asset = Asset(
        "body",
        "Body",
        Kind.PAINTING,
        ObjectRef(metadata, "cab", 1),
        Image.new("RGBA", (8, 8), "red"),
        Placement((0, 0), (8, 8)),
    )
    return Session(Project(metadata, "Sample", (8, 8), (0, 0), [asset]))


def test_open_project_prepares_first_preview_in_one_task(app, tmp_path, monkeypatch):
    from PySide6.QtCore import QCoreApplication, QThread

    from application.thumbnails import ThumbnailCache

    session = small_session(tmp_path)
    path = tmp_path / "saved.tachie.json"
    window = MainWindow(Settings(tmp_path / "settings.json"))
    states, phases, prepared = [], [], []
    window.tasks.busy_changed.connect(states.append)
    window.tasks.progress.connect(lambda message, current, total: phases.append(str(message)))

    def opened(cls, source, **kwargs):
        assert source == path
        assert QThread.currentThread() != app.thread()
        return session

    preview = session.preview
    thumbnails = ThumbnailCache.prepare

    def render(key=None, **kwargs):
        assert QThread.currentThread() != app.thread()
        prepared.append("preview")
        return preview(key, **kwargs)

    def prepare(cache, project):
        assert QThread.currentThread() != app.thread()
        prepared.append("thumbnails")
        return thumbnails(cache, project)

    monkeypatch.setattr(Session, "open", classmethod(opened))
    monkeypatch.setattr(session, "preview", render)
    monkeypatch.setattr(ThumbnailCache, "prepare", prepare)
    window.show()
    try:
        window.open_path(path)
        finish(app, window.tasks)
        assert states == [True, False]
        assert prepared == ["preview", "thumbnails"]
        reading = QCoreApplication.translate("Window", "Reading project…")
        generating = QCoreApplication.translate("Window", "Generating preview…")
        assert phases.index(reading) < phases.index(generating)
        assert window.session is session
        assert window.preview.canvas.item.pixmap().toImage().pixelColor(0, 0).red() == 255
        assert not window.sidebar.model.item(0).icon().isNull()
        window._request_preview()
        assert states == [True, False]  # First render also populates the normal preview cache.
    finally:
        window.close()


@pytest.mark.parametrize("cancel", [False, True])
def test_open_preview_failure_or_cancellation_keeps_current_project(app, tmp_path, monkeypatch, cancel):
    from pathlib import Path

    current = small_session(tmp_path)
    incoming = small_session(tmp_path)
    temporary = Path(incoming._temporary.name)
    window = MainWindow(Settings(tmp_path / "settings.json"))
    window.show()
    window._opened(current)
    finish(app, window.tasks)
    previous_image = window.preview.canvas.item.pixmap().cacheKey()
    monkeypatch.setattr(Session, "open", classmethod(lambda cls, *args, **kwargs: incoming))
    errors = []
    monkeypatch.setattr("ui.studio.window.error_dialog", lambda *args: errors.append(args[1]))

    def preview(*args, **kwargs):
        if cancel:
            window.tasks.cancel()
            return Image.new("RGBA", (8, 8), "blue")
        raise RuntimeError("Preview failed")

    monkeypatch.setattr(incoming, "preview", preview)
    try:
        window.open_path(tmp_path / "another.tachie.json")
        finish(app, window.tasks)
        assert window.session is current
        assert window._opening is None
        assert window.preview.canvas.item.pixmap().cacheKey() == previous_image
        assert not temporary.exists()
        assert bool(errors) is not cancel
        assert not window.progress.isVisible()
    finally:
        window.close()


def test_close_project_releases_preview_and_returns_home_then_reopens(app, tmp_path):
    from pathlib import Path

    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    window = MainWindow(Settings(tmp_path / "settings.json"))
    window.show()
    session = small_session(tmp_path)
    temporary = Path(session._temporary.name)
    window._opened(session)
    finish(app, window.tasks)
    assert window.close_project_button.isVisible()
    assert not window.preview.canvas.item.pixmap().isNull()
    window.close_project_button.click()
    assert window.session is None and window.isVisible()
    assert window.stack.currentWidget() is window.welcome
    assert window.preview.canvas.item.pixmap().isNull() and not window.preview.canvas._previews
    assert window.sidebar.model.rowCount() == 0 and not window.sidebar._thumbnail_icons
    assert not temporary.exists()
    assert not window.close_project_action.isEnabled()
    window._opened(small_session(tmp_path))
    finish(app, window.tasks)
    assert not window.preview.canvas.item.pixmap().isNull()
    window.activateWindow()
    app.processEvents()
    QTest.keyClick(window, Qt.Key.Key_W, Qt.KeyboardModifier.ControlModifier)
    assert window.session is None and window.isVisible()
    window.close()


@pytest.mark.parametrize("answer", ["Cancel", "Discard", "Save"])
def test_close_project_respects_unsaved_choice(app, tmp_path, monkeypatch, answer):
    import json
    from pathlib import Path

    from PySide6.QtWidgets import QFileDialog, QMessageBox

    window = MainWindow(Settings(tmp_path / "settings.json"))
    window.show()
    session = small_session(tmp_path)
    image_path = tmp_path / "replacement.png"
    Image.new("RGBA", (8, 8), "blue").save(image_path)
    session.import_images({"body": image_path})
    window._opened(session)
    finish(app, window.tasks)
    temporary = Path(session._temporary.name)
    saved_path = tmp_path / "saved.tachie.json"
    monkeypatch.setattr(QMessageBox, "exec", lambda _: getattr(QMessageBox.StandardButton, answer))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **kw: (str(saved_path), ""))
    window.close_project_button.click()
    finish(app, window.tasks)
    if answer == "Cancel":
        assert window.session is session and session.dirty and temporary.exists()
        monkeypatch.setattr(QMessageBox, "exec", lambda _: QMessageBox.StandardButton.Discard)
        window.close_project()
    else:
        assert window.session is None and not temporary.exists()
        assert window.stack.currentWidget() is window.welcome
    if answer == "Save":
        saved = json.loads(saved_path.read_text(encoding="utf-8"))
        assert (saved_path.parent / saved["sources"]["body"]).is_file()
    else:
        assert not saved_path.exists()
    window.close()


def test_application_menu_keeps_window_shortcuts_active(app, tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeySequence
    from PySide6.QtTest import QSignalSpy, QTest

    window = MainWindow(Settings(tmp_path / "settings.json"))
    window.show()
    window.activateWindow()
    app.processEvents()
    fit_action = next(action for action in window.actions() if action.shortcut() == QKeySequence("Ctrl+0"))
    triggered = QSignalSpy(fit_action.triggered)
    QTest.keyClick(window, Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier)
    assert triggered.count() == 1
    QTest.keyClick(window, Qt.Key.Key_F10)
    assert window.app_menu.isVisible()
    window.app_menu.hide()
    for item in (window.menu_button, window.theme_button):
        QTest.mouseClick(item, Qt.MouseButton.LeftButton, pos=item.rect().center())
        assert item.popup_menu.isVisible()
        item.popup_menu.hide()
    window.close()


@pytest.mark.parametrize("manual_zoom", [False, True])
def test_notices_preserve_canvas_size_zoom_and_pan(app, tmp_path, manual_zoom):
    from PySide6.QtCore import QCoreApplication, QEvent

    window = MainWindow(Settings(tmp_path / "settings.json"))
    window.show()
    window._opened(small_session(tmp_path))
    finish(app, window.tasks)
    window.feedback.hide()
    app.processEvents()
    if manual_zoom:
        window.preview.canvas.actual_size()
        window.preview.canvas.zoom_by(8)
        window.preview.canvas.centerOn(10, 12)

    def view_state():
        return (
            window.preview.canvas.viewport().size(),
            window.preview.canvas.transform(),
            window.preview.canvas.mapToScene(window.preview.canvas.viewport().rect().center()),
        )

    before = view_state()
    for message in ("Saved", "A longer message that wraps without resizing the canvas. " * 12):
        window._show_message(message)
        app.processEvents()
        assert view_state() == before
        assert window.notices.height() > 0
        assert window.feedback.geometry().height() > 0
        window._feedback_timer.timeout.emit()
        app.processEvents()
        assert window.feedback.isHidden()
        assert window.notices.height() == 0
        assert view_state() == before

    window._busy(True)
    window._task_notice_timer.timeout.emit()
    window._progress("Reading images", 1, 3)
    app.processEvents()
    assert view_state() == before
    window._busy(False)
    window._exported(tmp_path, "Export complete")
    app.processEvents()
    assert window.completion.isVisible()
    assert view_state() == before
    window.completion.hide()
    app.processEvents()
    assert window.notices.height() == 0
    assert view_state() == before
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_task_feedback_keeps_cancellation_available_without_status_bar(app, tmp_path):
    import threading

    from PySide6.QtWidgets import QStatusBar

    window = MainWindow(Settings(tmp_path / "settings.json"))
    window.show()
    release = threading.Event()

    def operation(progress):
        while not release.wait(0.01):
            progress("Reading images", 1, 3)

    try:
        window.tasks.start(operation, lambda result: pytest.fail("cancelled task completed"))
        deadline = time.monotonic() + 2
        while not window.feedback.isVisible() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.005)
        assert window.feedback.isVisible()
        assert window.feedback_text.text() == "Reading images"
        assert window.cancel_button.isVisible()
        assert not window.findChildren(QStatusBar)
        window.cancel_button.click()
        finish(app, window.tasks)
        assert not window.cancel_button.isVisible()
    finally:
        release.set()
        finish(app, window.tasks)
        window.close()


def test_rotated_crop_drag_follows_screen_direction(app):
    source = Image.new("RGBA", (400, 400))
    source.paste("white", (190, 190, 210, 210))
    presets = default_presets()
    presets["shipyardicon"] = IconPreset((100, 100), (0.5, 0.5), 1, 30)
    dialog = CropDialog(source, (200, 200), presets, {})
    before = clip_icon(source, (200, 200), presets["shipyardicon"]).getbbox()
    dialog._move(0.1, 0)
    after = clip_icon(source, (200, 200), dialog.presets["shipyardicon"]).getbbox()
    assert before is not None and after is not None
    assert (after[0] + after[2] - before[0] - before[2]) / 2 == pytest.approx(10, abs=0.5)
    assert (after[1] + after[3] - before[1] - before[3]) / 2 == pytest.approx(0, abs=0.5)
    dialog.close()


def test_crop_continuous_drag_renders_without_rebuilding_reference(app):
    from PySide6.QtTest import QTest

    source = Image.new("RGBA", (400, 400))
    source.paste((240, 50, 80, 128), (120, 80, 280, 320))
    presets = default_presets()
    reference = clip_icon(source, (200, 200), presets["shipyardicon"], True)
    dialog = CropDialog(source, (200, 200), presets, {"shipyardicon": reference})
    dialog.show()
    app.processEvents()
    assert not dialog.save_files.isChecked()
    reference_key = dialog.preview.reference.cacheKey()
    frames = set()
    for _ in range(20):
        dialog._move(0.0001, 0)
        QTest.qWait(5)
        frames.add(dialog.preview.image.cacheKey())
    assert len(frames) > 1  # Frames update during the gesture, not only after it stops.
    assert dialog.preview.reference.cacheKey() == reference_key
    assert dialog.presets["shipyardicon"].pivot[0] == pytest.approx(presets["shipyardicon"].pivot[0] + 0.002)
    dialog.preview.gesture_finished.emit()
    assert dialog.history_index == 1
    dialog._undo()
    assert dialog.presets == presets
    dialog.kind.setCurrentIndex(1)  # No reference for this portrait.
    assert dialog.preview.reference is None
    dialog.close()


def test_portrait_pixel_nudge_is_independent_of_view_zoom_and_rotation(app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    source = Image.new("RGBA", (400, 400), "blue")
    presets = default_presets()
    presets["shipyardicon"] = IconPreset((100, 100), (0.5, 0.5), 1, 30)
    reference = clip_icon(source, (200, 200), presets["shipyardicon"], True)
    dialog = CropDialog(source, (200, 200), presets, {"shipyardicon": reference})
    dialog.show()
    app.processEvents()
    dialog.view_zoom.setCurrentIndex(dialog.view_zoom.findData(4))
    app.processEvents()
    assert dialog.presets == presets and dialog.preview._ratio == 4
    QTest.keyClick(dialog.preview, Qt.Key.Key_Right)
    assert dialog.values["x"].value() == pytest.approx(1)
    assert dialog.values["y"].value() == pytest.approx(0)
    QTest.keyClick(dialog.preview, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
    assert dialog.values["y"].value() == pytest.approx(10)
    dialog.values["x"].setValue(2)
    dialog._sync_values()
    assert dialog.values["x"].value() == pytest.approx(2)
    assert dialog.values["y"].value() == pytest.approx(10)
    QTest.keyPress(dialog.preview, Qt.Key.Key_Space)
    assert dialog.preview.reference_only
    QTest.keyRelease(dialog.preview, Qt.Key.Key_Space)
    assert not dialog.preview.reference_only
    dialog.close()


def test_portrait_direct_gestures_select_target_rotate_and_reveal_references(app):
    from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
    from PySide6.QtGui import QMouseEvent, QWheelEvent
    from PySide6.QtTest import QTest

    source = Image.new("RGBA", (400, 400))
    source.paste("white", (215, 195, 225, 205))
    presets = default_presets()
    presets["squareicon"] = IconPreset((100, 100), (0.5, 0.5), 1)
    refs = {key: clip_icon(source, (200, 200), preset) for key, preset in presets.items()}
    dialog = CropDialog(source, (200, 200), presets, refs)
    dialog.show()
    app.processEvents()
    assert all(preview.isVisible() and preview._ratio == 1 for preview in dialog.previews.values())
    assert not dialog.precision.isVisible()
    target = dialog.previews["squareicon"]
    center = target._current_rect.center()
    start, end = center + QPointF(30, 0), center + QPointF(0, 30)
    QApplication.sendEvent(
        target,
        QMouseEvent(
            QEvent.Type.MouseButtonPress,
            start,
            QPointF(target.mapToGlobal(start.toPoint())),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.ControlModifier,
        ),
    )
    QApplication.sendEvent(
        target,
        QMouseEvent(
            QEvent.Type.MouseMove,
            end,
            QPointF(target.mapToGlobal(end.toPoint())),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.ControlModifier,
        ),
    )
    QTest.mouseRelease(target, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier, end.toPoint())
    assert dialog.kind.currentData() == "squareicon"
    assert dialog.presets["squareicon"].angle == pytest.approx(90)
    assert dialog.presets["shipyardicon"] == presets["shipyardicon"]
    rotated = clip_icon(source, (200, 200), dialog.presets["squareicon"])
    box = rotated.getbbox()
    assert box is not None and (box[1] + box[3]) / 2 == pytest.approx(30, abs=1)
    QTest.keyPress(target, Qt.Key.Key_Alt)
    assert all(preview.reference_only for preview in dialog.previews.values())
    QTest.keyRelease(target, Qt.Key.Key_Alt)
    assert not any(preview.reference_only for preview in dialog.previews.values())
    before = dialog.values["x"].value()
    QTest.keyClick(target, Qt.Key.Key_D)
    assert dialog.values["x"].value() == pytest.approx(before + 1)
    wide = dialog.previews["herohrzicon"]
    pos = wide._current_rect.center()
    QApplication.sendEvent(
        wide,
        QWheelEvent(
            pos,
            QPointF(wide.mapToGlobal(pos.toPoint())),
            QPoint(),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        ),
    )
    assert dialog.kind.currentData() == "herohrzicon"
    assert dialog.presets["herohrzicon"].scale == pytest.approx(presets["herohrzicon"].scale + 0.005)
    dialog._undo()
    assert dialog.presets["herohrzicon"] == presets["herohrzicon"]
    assert dialog.presets["squareicon"].angle == pytest.approx(90)
    dialog.close()


@pytest.mark.parametrize("save_files", [False, True])
def test_portrait_apply_only_asks_for_folder_when_requested(app, tmp_path, monkeypatch, save_files):
    from PySide6.QtWidgets import QDialog, QFileDialog

    session = small_session(tmp_path)
    window = MainWindow(Settings(tmp_path / "settings.json"))
    window._opened(session)
    finish(app, window.tasks)
    calls = []

    def accepted(dialog):
        assert not dialog.save_files.isChecked()
        dialog.save_files.setChecked(save_files)
        return QDialog.DialogCode.Accepted

    def folder(*args):
        assert save_files, "Applying without PNG export must not ask for a folder"
        return str(tmp_path)

    def clipped(reference, presets, output):
        calls.append(output)
        return [output / "portraits" / "squareicon.png"] if output else []

    monkeypatch.setattr(CropDialog, "exec", accepted)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", folder)
    monkeypatch.setattr(session, "clip_icons", clipped)
    window._crop(session, tmp_path / "reference.png", (Image.new("RGBA", (8, 8)), (4, 4)))
    finish(app, window.tasks)
    assert calls == [tmp_path if save_files else None]
    assert window.completion.isHidden() is not save_files
    window.close()


def test_preview_reuses_combined_image_and_invalidates_after_edits(app, tmp_path, monkeypatch):
    metadata = tmp_path / "sample"
    metadata.write_bytes(b"synthetic")

    def project(color):
        return Project(
            metadata,
            "Sample",
            (40, 60),
            (0, 0),
            [
                Asset(
                    "main",
                    "Main",
                    Kind.PAINTING,
                    ObjectRef(metadata, "cab", 1),
                    Image.new("RGBA", (40, 60), color),
                    Placement((0, 0), (40, 60)),
                ),
                Asset(
                    "other",
                    "Other",
                    Kind.PAINTING,
                    ObjectRef(metadata, "cab", 2),
                    Image.new("RGBA", (40, 60)),
                    Placement((0, 0), (40, 60)),
                ),
            ],
        )

    session = Session(project("red"))
    render = session.preview
    calls = []

    def counted(*args, **kwargs):
        calls.append((args, kwargs))
        return render(*args, **kwargs)

    monkeypatch.setattr(session, "preview", counted)
    window = MainWindow(Settings(tmp_path / "settings.json"))
    window.show()
    window._opened(session)
    finish(app, window.tasks)
    assert window.preview.preview_mode.currentData() is False
    window.preview.preview_mode.setCurrentIndex(1)
    finish(app, window.tasks)
    calls.clear()
    window.preview.canvas.clear_previews()
    window._request_preview()
    finish(app, window.tasks)
    assert len(calls) == 1
    window.selected_key = "other"
    window._request_preview()
    assert not window.tasks.busy
    assert len(calls) == 1  # Same combined artwork, different highlighted painting.
    window.preview.preview_mode.setCurrentIndex(0)
    finish(app, window.tasks)
    assert window.preview.canvas.item.pixmap().toImage().pixelColor(10, 10).alpha() == 0
    window.preview.preview_mode.setCurrentIndex(1)
    assert not window.tasks.busy
    assert len(calls) == 2

    replacement = tmp_path / "blue.png"
    Image.new("RGBA", (40, 60), "blue").save(replacement)
    window._edit(lambda: session.import_images({"main": replacement}), "Imported")
    finish(app, window.tasks)
    assert window.preview.canvas.item.pixmap().toImage().pixelColor(10, 10).blue() == 255
    window.inspector.preview_version.setCurrentIndex(1)
    finish(app, window.tasks)
    assert window.preview.canvas.item.pixmap().toImage().pixelColor(10, 10).red() == 255
    count = len(calls)
    window.inspector.preview_version.setCurrentIndex(0)
    assert not window.tasks.busy
    assert len(calls) == count
    assert window.preview.canvas.item.pixmap().toImage().pixelColor(10, 10).blue() == 255
    window.undo()
    finish(app, window.tasks)
    assert window.preview.canvas.item.pixmap().toImage().pixelColor(10, 10).red() == 255
    window.redo()
    finish(app, window.tasks)
    assert window.preview.canvas.item.pixmap().toImage().pixelColor(10, 10).blue() == 255
    window._opened(Session(project("green")))
    finish(app, window.tasks)
    assert window.preview.canvas.item.pixmap().toImage().pixelColor(10, 10).green() == 128
    window.close()


def test_preview_cache_evicts_least_recent_images_with_a_memory_limit(app):
    canvas = Canvas()
    canvas._preview_limit = 800  # Two 10 x 10 RGBA images.
    first, second, third = ((name, False, False) for name in ("first", "second", "third"))
    image = Image.new("RGBA", (10, 10), "red")
    canvas.set_image(image, first)
    canvas.set_image(image, second)
    assert canvas.show_cached(first)
    canvas.set_image(image, third)
    assert not canvas.show_cached(second)
    assert canvas.show_cached(first)
    assert canvas.show_cached(third)
    assert canvas._preview_bytes <= canvas._preview_limit
    canvas.clear_previews()
    assert not canvas.show_cached(first)
    assert canvas._preview_bytes == 0
    canvas.close()
