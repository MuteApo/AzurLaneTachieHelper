"""Shared dialog chrome preserves native dialog actions and busy cancellation."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from adapters.storage import Settings
from ui.dialogs.resource_pull import DeviceDialog
from ui.studio.window import MainWindow
from ui.widgets.chrome import WorkbenchDialog, WorkbenchMessageBox


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def dispose(widget):
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_shared_message_header_keeps_details_and_button_results(app):
    box = WorkbenchMessageBox()
    box.setWindowTitle("A longer confirmation title")
    box.setText("Save edits?")
    box.setDetailedText("Details about the unsaved changes.")
    box.setStandardButtons(QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel)
    box.show()
    app.processEvents()
    assert box.width() >= box.header.minimumSizeHint().width()
    details = next(
        button for button in box.buttons() if box.buttonRole(button) == QMessageBox.ButtonRole.ActionRole
    )
    QTest.mouseClick(details, Qt.MouseButton.LeftButton)
    app.processEvents()
    assert box.header.geometry().bottom() < box.layout().contentsMargins().top()
    QTest.mouseClick(box.button(QMessageBox.StandardButton.Save), Qt.MouseButton.LeftButton)
    assert box.result() == QMessageBox.StandardButton.Save
    box.show()
    app.processEvents()
    QTest.keyClick(box, Qt.Key.Key_Escape)
    assert box.result() == QMessageBox.StandardButton.Cancel
    dispose(box)


def test_shared_dialog_close_respects_active_task(app, tmp_path, monkeypatch):
    dialog = DeviceDialog(Settings(tmp_path / "settings.json"))
    dialog._initialized = True  # No device access in this test.
    cancelled = []
    monkeypatch.setattr(dialog.tasks, "cancel", lambda: cancelled.append(True))
    dialog.tasks.busy = True
    dialog.show()
    app.processEvents()
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    assert dialog.isVisible()
    dialog.close()
    assert dialog.isVisible() and len(cancelled) == 2
    dialog.tasks.busy = False
    dialog.close()
    assert not dialog.isVisible()
    dispose(dialog)


@pytest.mark.parametrize("kind", ["main", "dialog", "message"])
def test_windows_button_helper_has_no_system_caption(app, tmp_path, kind):
    """Exercise real Win32 styles across the transitions that exposed the blue bar."""
    if app.platformName() != "windows":
        pytest.skip("Requires QT_QPA_PLATFORM=windows and a Windows desktop")
    import ctypes
    from ctypes import wintypes

    from ui.theme import apply_theme

    native = ctypes.WinDLL("user32")
    native.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
    native.FindWindowExW.restype = wintypes.HWND
    native.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    native.GetWindowLongW.restype = wintypes.LONG
    native.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    native.SendMessageW.restype = wintypes.LPARAM
    native.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    native.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]

    if kind == "main":
        window = MainWindow(Settings(tmp_path / "settings.json"))
    elif kind == "dialog":
        window = WorkbenchDialog()
    else:
        window = WorkbenchMessageBox()
        window.setText("Test message")
        window.setStandardButtons(QMessageBox.StandardButton.Cancel)
    original_scheme = app.styleHints().colorScheme()

    def check_helper():
        hwnd = int(window.winId())
        helper = native.FindWindowExW(hwnd, None, "_q_titlebar", None)
        assert helper, "Review this regression when Qt changes its titlebar implementation"
        assert not native.GetWindowLongW(helper, -16) & 0x00C00000  # WS_CAPTION
        assert native.GetWindowLongW(helper, -20) & 0x00080000  # WS_EX_LAYERED: Qt buttons remain
        outer, client = wintypes.RECT(), wintypes.RECT()
        assert native.GetWindowRect(helper, ctypes.byref(outer))
        assert native.GetClientRect(helper, ctypes.byref(client))
        assert outer.bottom - outer.top == client.bottom  # No native title stealing button space.
        if kind != "message":
            assert native.GetWindowLongW(hwnd, -16) & 0x00040000  # WS_THICKFRAME
        return helper

    try:
        for theme in (Qt.ColorScheme.Light, Qt.ColorScheme.Dark):
            apply_theme(app, theme)
            window.show()
            app.processEvents()
            helper = check_helper()
            for active in (0, 1, 0, 1):
                native.SendMessageW(helper, 0x0086, active, 0)  # WM_NCACTIVATE
                window.setWindowTitle(f"Updated project {active}")
                app.processEvents()
                check_helper()
            if kind == "main":
                for command in (0xF030, 0xF120, 0xF020, 0xF120):  # Maximize, restore, minimize, restore.
                    native.SendMessageW(int(window.winId()), 0x0112, command, 0)
                    app.processEvents()
                    check_helper()
            window.hide()
        window.show()
        app.processEvents()
        check_helper()
        native.SendMessageW(int(window.winId()), 0x0112, 0xF060, 0)  # Native close still works.
        app.processEvents()
        assert not window.isVisible()
    finally:
        window.close()
        dispose(window)
        apply_theme(app, original_scheme)
