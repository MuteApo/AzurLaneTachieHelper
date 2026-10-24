"""Application-drawn window chrome shared by the studio and its dialogs."""

from typing import cast, override

from PySide6.QtCore import QCoreApplication, QEvent, QObject, Qt
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
from ui.widgets.window_controls import CaptionButton, position_resize_grips, resize_grips


class WindowHeader(QWidget):
    def __init__(self, window: QWidget):
        super().__init__(window)
        self.setObjectName("header")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._frameless = QApplication.platformName() == "windows"
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        content = QWidget(self)
        self.row = QHBoxLayout(content)
        self.row.setContentsMargins(22, 12, 22, 12)
        self.row.setSpacing(8)
        outer.addWidget(content, 1)
        self.minimize_button: CaptionButton | None = None
        self.maximize_button: CaptionButton | None = None
        self.close_button: CaptionButton | None = None
        if self._frameless:
            flags = window.windowFlags()
            window.setWindowFlags(
                (flags | Qt.WindowType.FramelessWindowHint)
                & ~(Qt.WindowType.ExpandedClientAreaHint | Qt.WindowType.NoTitleBarBackgroundHint)
            )
            controls = QWidget(self)
            buttons = QHBoxLayout(controls)
            buttons.setContentsMargins(0, 0, 0, 0)
            buttons.setSpacing(0)
            if flags & Qt.WindowType.WindowMinimizeButtonHint:
                self.minimize_button = CaptionButton("minimize", controls)
                self.minimize_button.clicked.connect(window.showMinimized)
                buttons.addWidget(self.minimize_button)
            if flags & Qt.WindowType.WindowMaximizeButtonHint:
                self.maximize_button = CaptionButton("maximize", controls)
                self.maximize_button.clicked.connect(self._toggle_maximized)
                buttons.addWidget(self.maximize_button)
            if flags & Qt.WindowType.WindowCloseButtonHint:
                self.close_button = CaptionButton("close", controls)
                self.close_button.clicked.connect(window.close)
                buttons.addWidget(self.close_button)
            outer.addWidget(controls, 0, Qt.AlignmentFlag.AlignTop)
            self._grips = resize_grips(window)
            window.installEventFilter(self)

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in (
            QEvent.Type.Show,
            QEvent.Type.Resize,
            QEvent.Type.WindowStateChange,
            QEvent.Type.LayoutRequest,
        ):
            self._sync_frame()
        return super().eventFilter(watched, event)

    def _sync_frame(self) -> None:
        window = self.window()
        if self.maximize_button:
            self.maximize_button.set_action("restore" if window.isMaximized() else "maximize")
        position_resize_grips(window, self._grips)

    def _toggle_maximized(self) -> None:
        window = self.window()
        if window.isMaximized():
            window.showNormal()
        else:
            window.showMaximized()

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._frameless and event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle and handle.startSystemMove():
                event.accept()
                return
        super().mousePressEvent(event)

    @override
    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if self.maximize_button and event.button() == Qt.MouseButton.LeftButton:
            self._toggle_maximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


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
    """The same application-drawn titlebar as the studio, with a content layout."""

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
