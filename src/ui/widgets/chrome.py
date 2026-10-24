"""A workbench header that shares the Windows titlebar's client area."""

from typing import cast, override

from PySide6.QtCore import QCoreApplication, Qt, Slot
from PySide6.QtGui import QMouseEvent, QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMessageBox,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from ui.i18n import render_message


class WindowHeader(QWidget):
    def __init__(self, window: QWidget):
        super().__init__(window)
        self.setObjectName("header")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ContentsMarginsRespectsSafeArea, False)
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(22, 12, 22, 12)
        self.row.setSpacing(8)
        self._buttons = max(
            1,
            sum(
                bool(window.windowFlags() & flag)
                for flag in (
                    Qt.WindowType.WindowMinimizeButtonHint,
                    Qt.WindowType.WindowMaximizeButtonHint,
                    Qt.WindowType.WindowCloseButtonHint,
                )
            ),
        )
        self._expanded = QApplication.platformName() == "windows"
        if self._expanded:
            window.setWindowFlags(
                window.windowFlags()
                | Qt.WindowType.ExpandedClientAreaHint
                | Qt.WindowType.NoTitleBarBackgroundHint
                | Qt.WindowType.CustomizeWindowHint
            )
            window.setAttribute(Qt.WidgetAttribute.WA_ContentsMarginsRespectsSafeArea, False)
            # Reserve space before the native handle is created; update from Qt on show.
            self.row.setContentsMargins(22, 12, 22 + 48 * self._buttons, 12)

    @override
    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        handle = self.window().windowHandle()
        if self._expanded and handle:
            # QWidget adds WindowTitleHint for system buttons. QWindow lets us keep
            # those buttons while omitting the duplicate title text and icon.
            handle.setFlag(Qt.WindowType.WindowTitleHint, False)
            _remove_helper_caption(int(handle.winId()))
            handle.safeAreaMarginsChanged.connect(self._reserve_controls, Qt.ConnectionType.UniqueConnection)
            self._reserve_controls()

    @Slot()
    def _reserve_controls(self):
        handle = self.window().windowHandle()
        if handle:
            # Each native caption button is 1.5 titlebar heights wide.
            # Keep the standard button allowance when fractional scaling rounds
            # the reported safe area down.
            buttons = round(max(32, handle.safeAreaMargins().top()) * 1.5 * self._buttons)
            self.row.setContentsMargins(22, 12, 22 + buttons, 12)

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._expanded and event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle and handle.startSystemMove():
                event.accept()
                return
        super().mousePressEvent(event)

    @override
    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if (
            self._expanded
            and event.button() == Qt.MouseButton.LeftButton
            and self.window().windowFlags() & Qt.WindowType.WindowMaximizeButtonHint
        ):
            window = self.window()
            if window.isMaximized():
                window.showNormal()
            else:
                window.showMaximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


def _remove_helper_caption(hwnd: int) -> None:
    """Remove the accidental Win32 caption on Qt's layered button window.

    Qt 6.12 creates `_q_titlebar` with style 0, which acquires WS_CAPTION,
    then reparents it without removing that style. Windows can paint a blue
    caption over Qt's transparent surface on activation or frame updates.
    Only this helper is changed; the main window keeps its native resize frame.
    """
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    find = user32.FindWindowExW
    find.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
    find.restype = wintypes.HWND
    helper = find(hwnd, None, "_q_titlebar", None)
    if not helper:  # Other Qt versions may not use this internal helper.
        return
    get_style = user32.GetWindowLongW
    get_style.argtypes = [wintypes.HWND, ctypes.c_int]
    get_style.restype = wintypes.LONG
    style = get_style(helper, -16)  # GWL_STYLE
    if not style & 0x00C00000:  # WS_CAPTION; already fixed by us or a newer Qt.
        return
    set_style = user32.SetWindowLongW
    set_style.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
    set_style.restype = wintypes.LONG
    if not set_style(helper, -16, style & ~0x00C00000):
        raise ctypes.WinError(ctypes.get_last_error())
    position = user32.SetWindowPos
    position.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    position.restype = wintypes.BOOL
    # FRAMECHANGED | NOMOVE | NOSIZE | NOZORDER | NOACTIVATE applies the style
    # without changing the helper's geometry, stacking order or keyboard focus.
    if not position(helper, None, 0, 0, 0, 0, 0x0037):
        raise ctypes.WinError(ctypes.get_last_error())


def _dialog_header(window: QWidget) -> WindowHeader:
    window.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
    header = WindowHeader(window)
    title = QLabel(window.windowTitle())
    title.setObjectName("brand")
    title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    window.windowTitleChanged.connect(title.setText)
    header.row.addWidget(title)
    header.row.addStretch()
    return header


class WorkbenchDialog(QDialog):
    """The same native integrated titlebar as the workbench, with a content layout."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.header = _dialog_header(self)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self.header)
        content = QWidget(self)
        self.body = QVBoxLayout(content)
        self.body.setContentsMargins(24, 24, 24, 24)
        self.body.setSpacing(12)
        root.addWidget(content, 1)


class WorkbenchMessageBox(QMessageBox):
    """Retain Qt's message-box buttons and result semantics under the shared header."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOption(QMessageBox.Option.DontUseNativeDialog)
        self.header = _dialog_header(self)
        self._content_top: int | None = None
        self._title_space = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

    def _position_header(self):
        self.header.setGeometry(0, 0, self.width(), self.header.sizeHint().height())
        self.header.raise_()

    @override
    def showEvent(self, event: QShowEvent) -> None:
        layout = cast(QLayout, self.layout())
        margins = layout.contentsMargins()
        if self._content_top is None:
            self._content_top = margins.top()
            grid = cast(QGridLayout, layout)
            grid.addItem(self._title_space, grid.rowCount(), 0, 1, grid.columnCount())
        self._title_space.changeSize(
            self.header.minimumSizeHint().width(), 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed
        )
        layout.setContentsMargins(
            margins.left(),
            self._content_top + self.header.sizeHint().height(),
            margins.right(),
            margins.bottom(),
        )
        super().showEvent(event)
        self._position_header()

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._position_header()


def error_dialog(parent, error, details: str = ""):
    box = WorkbenchMessageBox(parent)
    box.setWindowTitle(QCoreApplication.translate("Dialogs", "Operation incomplete"))
    box.setIcon(QMessageBox.Icon.Warning)
    box.setText(render_message(error))
    box.setInformativeText(
        QCoreApplication.translate("Dialogs", "Your edits are preserved. Review the message and try again.")
    )
    if details:
        box.setDetailedText(details)
    box.exec()
