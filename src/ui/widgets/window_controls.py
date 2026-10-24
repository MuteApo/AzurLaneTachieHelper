"""Caption buttons and resize grips for the Windows frameless workbench."""

from typing import Literal, override

from PySide6.QtCore import QCoreApplication, QEvent, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QAbstractButton, QWidget

from ui.theme import COLORS

type CaptionAction = Literal["minimize", "maximize", "restore", "close"]


class CaptionButton(QAbstractButton):
    def __init__(self, action: CaptionAction, parent: QWidget):
        super().__init__(parent)
        self.setFixedSize(46, 34)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.set_action(action)

    def set_action(self, action: CaptionAction) -> None:
        self.action = action
        labels = {
            "minimize": QCoreApplication.translate("WindowChrome", "Minimize"),
            "maximize": QCoreApplication.translate("WindowChrome", "Maximize"),
            "restore": QCoreApplication.translate("WindowChrome", "Restore"),
            "close": QCoreApplication.translate("WindowChrome", "Close"),
        }
        self.setAccessibleName(labels[action])
        self.setToolTip(labels[action])
        self.update()

    @override
    def event(self, event: QEvent) -> bool:
        if event.type() in (QEvent.Type.Enter, QEvent.Type.Leave):
            self.update()
        return super().event(event)

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        variant = 0 if self.palette().window().color().lightness() < 128 else 1
        ink = COLORS["text" if self.isEnabled() else "disabled_text"][variant]
        painter = QPainter(self)
        if self.isEnabled() and (self.underMouse() or self.isDown()):
            role = "pressed" if self.isDown() else "hover"
            if self.action == "close":
                role = "danger"
                ink = COLORS["danger_text"][variant]
            painter.fillRect(self.rect(), QColor(COLORS[role][variant]))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(ink), 1.2))
        painter.translate(self.width() / 2, self.height() / 2)
        if self.action == "minimize":
            painter.drawLine(QPointF(-5, 0), QPointF(5, 0))
        elif self.action == "maximize":
            painter.drawRect(QRectF(-4.5, -4.5, 9, 9))
        elif self.action == "restore":
            painter.drawLine(QPointF(-2, -5), QPointF(5, -5))
            painter.drawLine(QPointF(5, -5), QPointF(5, 2))
            painter.drawRect(QRectF(-5, -2, 7, 7))
        else:
            painter.drawLine(QPointF(-4, -4), QPointF(4, 4))
            painter.drawLine(QPointF(-4, 4), QPointF(4, -4))


class ResizeGrip(QWidget):
    """A transparent edge hit target; the OS performs the interactive resize."""

    def __init__(self, window: QWidget, edges: Qt.Edge, cursor: Qt.CursorShape):
        super().__init__(window)
        self.edges = edges
        self.setCursor(cursor)

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        handle = self.window().windowHandle()
        if event.button() == Qt.MouseButton.LeftButton and handle and handle.startSystemResize(self.edges):
            event.accept()
            return
        super().mousePressEvent(event)


def resize_grips(window: QWidget) -> list[ResizeGrip]:
    left, top, right, bottom = Qt.Edge.LeftEdge, Qt.Edge.TopEdge, Qt.Edge.RightEdge, Qt.Edge.BottomEdge
    return [
        ResizeGrip(window, edges, cursor)
        for edges, cursor in (
            (left, Qt.CursorShape.SizeHorCursor),
            (right, Qt.CursorShape.SizeHorCursor),
            (top, Qt.CursorShape.SizeVerCursor),
            (bottom, Qt.CursorShape.SizeVerCursor),
            (top | left, Qt.CursorShape.SizeFDiagCursor),
            (top | right, Qt.CursorShape.SizeBDiagCursor),
            (bottom | left, Qt.CursorShape.SizeBDiagCursor),
            (bottom | right, Qt.CursorShape.SizeFDiagCursor),
        )
    ]


def position_resize_grips(window: QWidget, grips: list[ResizeGrip]) -> None:
    width, height, edge, corner = window.width(), window.height(), 6, 10
    horizontal = window.minimumWidth() < window.maximumWidth()
    vertical = window.minimumHeight() < window.maximumHeight()
    x = corner if horizontal else 0
    y = corner if vertical else 0
    rectangles = (
        (0, y, edge, height - 2 * y),
        (width - edge, y, edge, height - 2 * y),
        (x, 0, width - 2 * x, edge),
        (x, height - edge, width - 2 * x, edge),
        (0, 0, corner, corner),
        (width - corner, 0, corner, corner),
        (0, height - corner, corner, corner),
        (width - corner, height - corner, corner, corner),
    )
    resizable = not (window.isMaximized() or window.isFullScreen())
    for grip, rect in zip(grips, rectangles, strict=True):
        allowed = resizable
        if grip.edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge):
            allowed = allowed and horizontal
        if grip.edges & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge):
            allowed = allowed and vertical
        grip.setGeometry(*rect)
        grip.setVisible(allowed)
        if allowed:
            grip.raise_()
