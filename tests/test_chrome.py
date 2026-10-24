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
    if dialog.header.close_button:
        QTest.mouseClick(dialog.header.close_button, Qt.MouseButton.LeftButton)
    else:
        dialog.close()
    assert dialog.isVisible() and len(cancelled) == 2
    dialog.tasks.busy = False
    dialog.close()
    assert not dialog.isVisible()
    dispose(dialog)


@pytest.mark.parametrize("kind", ["main", "dialog", "message"])
def test_windows_has_no_native_caption_or_frame(app, tmp_path, kind):
    """Exercise real Win32 styles across the transitions that exposed the blue bar."""
    if app.platformName() != "windows":
        pytest.skip("Requires QT_QPA_PLATFORM=windows and a Windows desktop")
    import ctypes
    from ctypes import wintypes

    from ui.theme import apply_theme
    from ui.widgets.window_controls import ResizeGrip

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
        window.resize(400, 300)
    else:
        window = WorkbenchMessageBox()
        window.setText("Test message")
        window.setStandardButtons(QMessageBox.StandardButton.Cancel)
    original_scheme = app.styleHints().colorScheme()

    def check_frame():
        hwnd = int(window.winId())
        assert window.windowFlags() & Qt.WindowType.FramelessWindowHint
        assert not window.windowFlags() & Qt.WindowType.ExpandedClientAreaHint
        assert not native.GetWindowLongW(hwnd, -16) & 0x00C40000  # No WS_CAPTION / WS_THICKFRAME.
        assert not native.FindWindowExW(hwnd, None, "_q_titlebar", None)
        outer, client = wintypes.RECT(), wintypes.RECT()
        assert native.GetWindowRect(hwnd, ctypes.byref(outer))
        assert native.GetClientRect(hwnd, ctypes.byref(client))
        assert outer.right - outer.left == client.right
        assert outer.bottom - outer.top == client.bottom

    try:
        # Native handles can exist before the header's showEvent. No system caption
        # may be drawn during the first show, or when Qt recreates those handles.
        check_frame()
        window.destroy()
        check_frame()
        for theme in (Qt.ColorScheme.Light, Qt.ColorScheme.Dark):
            apply_theme(app, theme)
            window.show()
            app.processEvents()
            check_frame()
            for active in (0, 1, 0, 1):
                native.SendMessageW(int(window.winId()), 0x0086, active, 0)  # WM_NCACTIVATE
                native.SendMessageW(int(window.winId()), 0x0085, 1, 0)  # WM_NCPAINT
                window.setWindowTitle(f"Updated project {active}")
                app.processEvents()
                check_frame()
            grips = window.findChildren(ResizeGrip)
            if kind == "message":
                assert not any(grip.isVisible() for grip in grips)
            else:
                assert len([grip for grip in grips if grip.isVisible()]) == 8
            if kind == "main":
                QTest.mouseClick(window.header.maximize_button, Qt.MouseButton.LeftButton)
                app.processEvents()
                assert window.isMaximized()
                assert window.header.maximize_button.action == "restore"
                assert not any(grip.isVisible() for grip in grips)
                assert window.screen().availableGeometry().contains(window.frameGeometry())
                check_frame()
                QTest.mouseClick(window.header.maximize_button, Qt.MouseButton.LeftButton)
                app.processEvents()
                assert not window.isMaximized()
                assert window.header.maximize_button.action == "maximize"
                assert all(grip.isVisible() for grip in grips)
                QTest.mouseDClick(window.header, Qt.MouseButton.LeftButton)
                assert window.isMaximized()
                QTest.mouseDClick(window.header, Qt.MouseButton.LeftButton)
                assert not window.isMaximized()
                QTest.mouseClick(window.header.minimize_button, Qt.MouseButton.LeftButton)
                app.processEvents()
                assert window.isMinimized()
                window.showNormal()
                app.processEvents()
                check_frame()
            window.hide()
        window.show()
        app.processEvents()
        check_frame()
        QTest.mouseClick(window.header.close_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert not window.isVisible()
        if kind == "message":
            assert window.result() == QMessageBox.StandardButton.Cancel
    finally:
        window.close()
        dispose(window)
        apply_theme(app, original_scheme)


def test_frameless_drag_resize_and_fixed_size(app, monkeypatch):
    from PySide6.QtCore import QPoint

    from ui.widgets.window_controls import ResizeGrip

    monkeypatch.setattr(QApplication, "platformName", lambda: "windows")
    window = WorkbenchDialog()
    window.resize(400, 300)
    window.show()
    app.processEvents()
    moves, resizes = [], []
    handle = window.windowHandle()
    monkeypatch.setattr(handle, "startSystemMove", lambda: moves.append(True) or True)
    monkeypatch.setattr(handle, "startSystemResize", lambda edges: resizes.append(edges) or True)
    try:
        QTest.mousePress(window.header, Qt.MouseButton.LeftButton, pos=QPoint(100, 20))
        QTest.mouseRelease(window.header, Qt.MouseButton.LeftButton, pos=QPoint(100, 20))
        assert moves == [True]
        grips = window.findChildren(ResizeGrip)
        for grip in grips:
            point = grip.geometry().center()
            assert window.childAt(point) is grip
            QTest.mousePress(grip, Qt.MouseButton.LeftButton)
            QTest.mouseRelease(grip, Qt.MouseButton.LeftButton)
        assert set(resizes) == {grip.edges for grip in grips}
        window.hide()
        window.setFixedSize(window.size())
        window.show()
        app.processEvents()
        assert not any(grip.isVisible() for grip in grips)
    finally:
        monkeypatch.undo()  # Restore methods before deleting their Qt owner.
        window.close()
        dispose(window)
