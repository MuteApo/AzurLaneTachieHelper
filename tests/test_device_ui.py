"""Automatic discovery and completion use simulated devices, never real ADB."""

import os
import threading
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from adapters.adb import PullResult
from adapters.storage import Settings
from ui.dialogs.resource_pull import DeviceDialog
from ui.widgets.controls import SearchComboBox


@pytest.fixture
def app(monkeypatch):
    application = QApplication.instance() or QApplication([])

    def unexpected(*args, **kwargs):
        raise AssertionError("Tests must not access real ADB")

    monkeypatch.setattr("ui.dialogs.resource_pull.AdbClient._server", unexpected)
    return application


def finish(app, dialog):
    app.processEvents()
    deadline = time.monotonic() + 5
    while dialog.tasks.busy and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    assert not dialog.tasks.busy
    app.processEvents()


def close(dialog):
    dialog.close()
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def settings_for(tmp_path, **values):
    settings = Settings(tmp_path / "settings.json")
    settings.update({"server": "JP", "pull_directory": str(tmp_path / "projects"), **values})
    return settings


def test_open_discovers_devices_and_typing_shows_local_completions(app, tmp_path, monkeypatch):
    index = tmp_path / "dependencies"
    index.write_bytes(b"fixture")
    monkeypatch.setattr(
        "application.resource_pull.dependency_index",
        lambda path: {
            "painting/portland": (),
            "painting/portland_n": (),
            "painting/portland_hx": (),
            "painting/portland_tex": (),
            "painting/aidang_2": (),
            "paintingface/portland": (),
        },
    )
    calls = []

    class Device:
        def devices(self):
            calls.append("devices")
            return ["emulator-5554"]

    settings = settings_for(tmp_path, manifest_path=str(index))
    dialog = DeviceDialog(settings)
    monkeypatch.setattr(dialog, "_client", Device)
    dialog.show()
    finish(app, dialog)
    assert calls == ["devices"]
    assert dialog.serial.findData("emulator-5554") >= 0
    assert dialog._serial_value() == "emulator-5554"
    assert dialog.destination.text() == str(tmp_path / "projects" / "download")
    assert [dialog.name.itemText(i) for i in range(dialog.name.count())] == ["aidang_2", "portland"]
    dialog.name.lineEdit().setFocus()
    QTest.keyClicks(dialog.name.lineEdit(), "LAND")
    app.processEvents()
    completer = dialog.name.completer()
    assert completer.completionCount() == 1
    assert completer.currentCompletion() == "portland"
    assert completer.popup().isVisible()
    completer.popup().hide()
    (tmp_path / "projects" / "portland").mkdir(parents=True)
    dialog.name.setCurrentText("portland")
    assert dialog.destination.text() == str(tmp_path / "projects" / "portland-2")
    dialog.destination.setText(str(tmp_path / "chosen"))
    dialog.destination.textEdited.emit(dialog.destination.text())
    dialog.name.setCurrentText("aidang_2")
    assert dialog.destination.text() == str(tmp_path / "chosen")
    close(dialog)


def test_missing_index_loads_automatically_and_refresh_uses_private_cache(app, tmp_path, monkeypatch):
    monkeypatch.setattr("application.resource_pull.dependency_index", lambda path: {"painting/portland": ()})
    calls = []

    class Device:
        def devices(self):
            return ["emulator-5554"]

        def connect(self):
            calls.append("connect")

        def pull_dependencies(self, destination):
            destination.mkdir(parents=True, exist_ok=True)
            path = destination / "dependencies"
            path.write_bytes(b"index")
            calls.append(path)
            return path

    settings = settings_for(tmp_path)
    dialog = DeviceDialog(settings)
    monkeypatch.setattr(dialog, "_client", Device)
    dialog.name.setCurrentText("custom_hx")
    dialog.show()
    finish(app, dialog)
    assert dialog.name.currentText() == "custom_hx"
    assert dialog.name.findText("portland") >= 0
    first = dialog._index_cache()
    assert first.read_bytes() == b"index"
    assert not Path(dialog.destination.text()).exists()
    dialog.names_button.click()
    finish(app, dialog)
    assert calls.count("connect") == 2
    assert settings.get("manifest_path") == ""
    dialog.server.setCurrentText("EN")
    finish(app, dialog)
    assert dialog._index_cache() != first
    assert dialog._index_cache().is_file() and first.is_file()
    count = len(calls)
    dialog.package.editingFinished.emit()
    finish(app, dialog)
    assert len(calls) == count
    close(dialog)


def test_multiple_devices_default_to_first_and_allow_switching(app, tmp_path, monkeypatch):
    monkeypatch.setattr("application.resource_pull.dependency_index", lambda path: {"painting/portland": ()})
    selected = []

    class Device:
        def devices(self):
            return ["one", "two"]

        def connect(self):
            selected.append("connect")

        def pull_dependencies(self, destination):
            path = destination / "dependencies"
            path.write_bytes(b"index")
            return path

    dialog = DeviceDialog(settings_for(tmp_path))
    monkeypatch.setattr(dialog, "_client", Device)
    dialog.show()
    finish(app, dialog)
    assert dialog._serial_value() == "one" and selected == ["connect"]
    assert dialog.serial.count() == 3
    dialog.serial.setCurrentIndex(dialog.serial.findData("two"))
    dialog.serial.activated.emit(dialog.serial.currentIndex())
    finish(app, dialog)
    assert selected == ["connect", "connect"] and dialog._serial_value() == "two"
    assert dialog.name.findText("portland") >= 0
    dialog.serial.setCurrentIndex(0)
    dialog.serial.activated.emit(0)
    finish(app, dialog)
    assert dialog._serial_value() == "one"
    assert selected == ["connect", "connect"]  # First device's index is already cached.
    close(dialog)


def test_editable_combo_clicks_open_choices_and_typing_still_filters(app):
    combo = SearchComboBox()
    combo.addItem("First device", "first")
    combo.addItem("Second device", "second")
    combo.resize(300, 40)
    combo.show()
    app.processEvents()
    editor = combo.lineEdit()
    popup = combo.completer().popup()
    selected = []
    combo.activated.connect(selected.append)
    QTest.mouseClick(editor, Qt.MouseButton.LeftButton)
    app.processEvents()
    assert popup.isVisible()
    QTest.keyClick(editor, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClicks(editor, "Second")
    app.processEvents()
    assert combo.completer().completionCount() == 1
    target = popup.model().index(0, 0)
    QTest.mouseClick(popup.viewport(), Qt.MouseButton.LeftButton, pos=popup.visualRect(target).center())
    app.processEvents()
    assert combo.currentData() == "second" and selected == [1]
    QTest.mouseClick(combo, Qt.MouseButton.LeftButton, pos=QPoint(combo.width() - 12, combo.height() // 2))
    app.processEvents()
    assert popup.isVisible() and combo.completer().completionCount() == 2
    QTest.keyClick(popup, Qt.Key.Key_Escape)
    app.processEvents()
    assert not popup.isVisible()
    close(combo)


def test_discovery_failure_still_loads_local_index_without_retries(app, tmp_path, monkeypatch):
    index = tmp_path / "dependencies"
    index.write_bytes(b"broken")
    calls = []

    def read(path):
        calls.append(path)
        raise ValueError("Invalid index")

    class Device:
        def devices(self):
            raise RuntimeError("ADB unavailable")

    monkeypatch.setattr("application.resource_pull.dependency_index", read)
    dialog = DeviceDialog(settings_for(tmp_path, manifest_path=str(index)))
    monkeypatch.setattr(dialog, "_client", Device)
    monkeypatch.setattr(
        "ui.dialogs.resource_pull.error_dialog", lambda *args: pytest.fail("No startup modal")
    )
    dialog.show()
    finish(app, dialog)
    assert calls == [index]
    assert dialog.status.text() == "Invalid index"
    assert dialog.names_button.isEnabled()
    close(dialog)


def test_busy_locks_connection_and_preserves_explicit_unavailable_device(app, tmp_path, monkeypatch):
    released = threading.Event()

    class Device:
        def devices(self):
            released.wait(2)
            return ["another-device"]

    settings = settings_for(tmp_path, serial="chosen-device", adb_path="custom/adb.exe")
    dialog = DeviceDialog(settings)
    client = dialog._client()
    assert client.executable == "custom/adb.exe" and client.apk_fallback
    monkeypatch.setattr(dialog, "_client", Device)
    dialog.show()
    app.processEvents()
    assert dialog.tasks.busy
    assert not dialog.connection_toggle.isEnabled() and not dialog.package.isEnabled()
    assert not dialog.names_button.isEnabled() and not dialog.pull_button.isEnabled()
    released.set()
    finish(app, dialog)
    assert dialog._serial_value() == "chosen-device"
    assert dialog.serial.findData("another-device") >= 0
    close(dialog)


def test_download_keeps_index_with_project_and_remembers_destination(app, tmp_path, monkeypatch):
    index = {"painting/portland": ()}
    monkeypatch.setattr("application.resource_pull.dependency_index", lambda path: index)

    class Device:
        def connect(self):
            pass

        def pull_dependencies(self, destination):
            destination.mkdir(parents=True)
            path = destination / "dependencies"
            path.write_bytes(b"fresh index")
            return path

        def pull_project(self, name, dependencies, destination, progress):
            assert dependencies == index
            metadata = destination / name
            metadata.write_bytes(b"metadata")
            return PullResult(metadata, [metadata], [])

    settings = settings_for(tmp_path)
    dialog = DeviceDialog(settings)
    monkeypatch.setattr(dialog, "_client", Device)
    dialog.name.setCurrentText("portland")
    dialog.pull_button.click()
    finish(app, dialog)
    destination = tmp_path / "projects" / "portland"
    assert dialog.metadata == destination / "portland"
    assert (destination / "dependencies").read_bytes() == b"fresh index"
    assert settings.get("manifest_path") == str((destination / "dependencies").resolve())
    assert settings.get("pull_directory") == str(destination.parent.resolve())
    assert dialog.open_button.isEnabled()
    close(dialog)
