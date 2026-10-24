"""Small workbench controls shared by the Qt layout."""

from typing import cast, override

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QCompleter,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SearchComboBox(QComboBox):
    """Click either the editor or arrow to browse; typing filters the same popup."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        editor = QLineEdit(self)
        self.setLineEdit(editor)
        editor.installEventFilter(self)
        completer = QCompleter(self.model(), self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setMaxVisibleItems(8)
        cast(QAbstractItemView, completer.popup()).setObjectName("completionPopup")
        self.setCompleter(completer)

    @override
    def showPopup(self) -> None:
        completer = cast(QCompleter, self.completer())
        completer.setCompletionPrefix("")
        completer.complete()

    @override
    def hidePopup(self) -> None:
        cast(QAbstractItemView, cast(QCompleter, self.completer()).popup()).hide()
        super().hidePopup()

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.lineEdit() and event.type() == QEvent.Type.MouseButtonRelease:
            if cast(QMouseEvent, event).button() == Qt.MouseButton.LeftButton:
                self.showPopup()
        return super().eventFilter(watched, event)


class NoticeOverlay(QWidget):
    """Size only the floating notices, leaving the workspace layout untouched."""

    def __init__(self, workspace: QWidget, notices: list[QWidget]):
        super().__init__(workspace)
        self.workspace = workspace
        self.stack = QVBoxLayout(self)
        self.stack.setContentsMargins(0, 0, 0, 0)
        self.stack.setSpacing(8)
        self.stack.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        for notice in notices:
            self.stack.addWidget(notice)
        workspace.installEventFilter(self)
        self._position()
        self.raise_()

    def _position(self):
        width = min(760, max(0, self.workspace.width() - 32))
        height = self.stack.heightForWidth(width)
        if height < 0:
            height = self.stack.sizeHint().height()
        self.setGeometry((self.workspace.width() - width) // 2, 12, width, max(0, height))

    @override
    def event(self, event: QEvent) -> bool:
        result = super().event(event)
        if event.type() == QEvent.Type.LayoutRequest:
            self._position()
        return result

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Resize:
            self._position()
        return super().eventFilter(watched, event)


class PopupButton(QPushButton):
    """The entire button opens its menu, without a separate arrow hit target."""

    def __init__(self, menu: QMenu, parent=None):
        super().__init__(parent)
        self.popup_menu = menu
        self.clicked.connect(self.show_popup)

    def show_popup(self):
        self.popup_menu.popup(self.mapToGlobal(self.rect().bottomLeft()))


class SegmentedChoice[T](QWidget):
    """A compact, keyboard-accessible choice with one selected option."""

    currentIndexChanged = Signal(int)

    def __init__(self, options: list[tuple[str, T]], parent=None):
        super().__init__(parent)
        self.setObjectName("segment")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._values = [value for _, value in options]
        self._group = QButtonGroup(self)
        row = QHBoxLayout(self)
        row.setContentsMargins(3, 3, 3, 3)
        row.setSpacing(2)
        for index, (title, _) in enumerate(options):
            item = QPushButton(title)
            item.setObjectName("segmentOption")
            item.setCheckable(True)
            self._group.addButton(item, index)
            row.addWidget(item)
        self._group.button(0).setChecked(True)
        self._group.idToggled.connect(self._changed)

    def _changed(self, index: int, checked: bool):
        if checked:
            self.currentIndexChanged.emit(index)

    def currentData(self) -> T:
        return self._values[self.currentIndex()]

    def currentIndex(self) -> int:
        return self._group.checkedId()

    def setCurrentIndex(self, index: int):
        self._group.button(index).setChecked(True)

    def setCurrentData(self, value: T) -> None:
        self.setCurrentIndex(self._values.index(value))


def icon(name: str, color: QColor, disabled_color: QColor) -> QIcon:
    paths = {
        "export": [[(10, 13), (10, 3)], [(6, 7), (10, 3), (14, 7)], [(4, 11), (4, 17), (16, 17), (16, 11)]],
        "replace": [[(4, 6), (16, 6), (13, 3)], [(16, 14), (4, 14), (7, 17)]],
        "layers": [
            [(3, 7), (10, 3), (17, 7), (10, 11), (3, 7)],
            [(3, 11), (10, 15), (17, 11)],
            [(3, 15), (10, 19), (17, 15)],
        ],
        "crop": [[(6, 2), (6, 14), (18, 14)], [(2, 6), (14, 6), (14, 18)]],
        "folder": [[(2, 5), (8, 5), (10, 7), (18, 7), (18, 16), (2, 16), (2, 5)]],
        "minus": [[(5, 10), (15, 10)]],
        "plus": [[(5, 10), (15, 10)], [(10, 5), (10, 15)]],
        "theme": [[(10, 3), (10, 17)]],
        "undo": [[(7, 3), (3, 7), (7, 11)], [(3, 7), (12, 7), (16, 10), (16, 15)]],
        "redo": [[(13, 3), (17, 7), (13, 11)], [(17, 7), (8, 7), (4, 10), (4, 15)]],
    }
    result = QIcon()
    for mode, ink in ((QIcon.Mode.Normal, color), (QIcon.Mode.Disabled, disabled_color)):
        image = QPixmap(40, 40)
        image.fill(Qt.GlobalColor.transparent)
        image.setDevicePixelRatio(2)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(
            QPen(ink, 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        )
        for points in paths[name]:
            for start, end in zip(points, points[1:]):
                painter.drawLine(QPointF(*start), QPointF(*end))
        if name == "theme":
            painter.drawEllipse(QRectF(3, 3, 14, 14))
        painter.end()
        result.addPixmap(image, mode)
    return result


def label(text: str, role: str = "muted") -> QLabel:
    widget = QLabel(text)
    widget.setObjectName(role)
    return widget


def button(text: str, callback, primary: bool = False) -> QPushButton:
    widget = QPushButton(text)
    if primary:
        widget.setObjectName("primary")
    widget.clicked.connect(callback)
    return widget


def with_icon[T: QWidget](widget: T, name: str) -> T:
    widget.setProperty("glyph", name)
    return widget
