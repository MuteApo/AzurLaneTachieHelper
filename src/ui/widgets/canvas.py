from collections import OrderedDict
from pathlib import Path
from typing import override

from PIL import Image
from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QImage,
    QPainter,
    QPaintEvent,
    QPalette,
    QPen,
    QPixmap,
    QResizeEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

type PreviewKey = tuple[str | None, bool, bool]


def pixmap(image: Image.Image) -> QPixmap:
    rgba = image if image.mode == "RGBA" else image.convert("RGBA")
    data = rgba.tobytes()
    return QPixmap.fromImage(
        QImage(data, rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888)
    )


class Canvas(QGraphicsView):
    zoom_changed = Signal(float)
    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.item = QGraphicsPixmapItem()
        self.scene().addItem(self.item)
        pen = QPen(self.palette().color(QPalette.ColorRole.Link), 1.5, Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        self.boundary = self.scene().addRect(QRectF(), pen)
        self.boundary.setZValue(2)
        self.boundary.hide()
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self._size = (0, 0)
        self._fit = True
        self._view_key: PreviewKey | None = None
        self._actual_size_default = False
        self.checker = True
        self._previews: OrderedDict[PreviewKey, QPixmap] = OrderedDict()
        self._preview_bytes = 0
        self._preview_limit = 256 * 1024 * 1024
        self.setAcceptDrops(True)
        self.drop_enabled = True
        self.drop_hint = ""
        self._drop_active = False

    def set_drop_active(self, active: bool):
        self._drop_active = active
        self.viewport().update()

    @override
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self.drop_enabled and any(url.isLocalFile() for url in event.mimeData().urls()):
            self.set_drop_active(True)
            event.acceptProposedAction()
        else:
            event.ignore()

    @override
    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if self.drop_enabled and self._drop_active:
            event.acceptProposedAction()
        else:
            event.ignore()

    @override
    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self.set_drop_active(False)
        event.accept()

    @override
    def dropEvent(self, event: QDropEvent) -> None:
        self.set_drop_active(False)
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        if self.drop_enabled and paths:
            event.acceptProposedAction()
            self.files_dropped.emit(paths)
        else:
            event.ignore()

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        if not self._drop_active:
            return
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = QRectF(self.viewport().rect()).adjusted(12, 12, -12, -12)
        surface = self.palette().color(QPalette.ColorRole.Window)
        surface.setAlpha(235)
        painter.setBrush(surface)
        painter.setPen(QPen(self.palette().color(QPalette.ColorRole.Link), 2, Qt.PenStyle.DashLine))
        painter.drawRoundedRect(area, 10, 10)
        font = painter.font()
        font.setPixelSize(16)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(self.palette().color(QPalette.ColorRole.Text))
        painter.drawText(area.adjusted(24, 24, -24, -24), Qt.AlignmentFlag.AlignCenter, self.drop_hint)
        painter.end()

    def clear_previews(self):
        self._previews.clear()
        self._preview_bytes = 0

    def clear(self):
        self.clear_previews()
        self.item.setPixmap(QPixmap())
        self.boundary.hide()
        self._size = (0, 0)
        self._fit = True
        self._view_key = None
        self._actual_size_default = False
        self.resetTransform()
        self.setSceneRect(QRectF())

    def show_cached(self, key: PreviewKey, *, actual_size: bool = False) -> bool:
        if key not in self._previews:
            return False
        self._previews.move_to_end(key)
        self._show_pixmap(self._previews[key], key, actual_size)
        return True

    def set_image(self, image: Image.Image, key: PreviewKey, *, actual_size: bool = False):
        """Cache the final Qt image so a hit skips both rendering and pixel conversion."""
        rendered = pixmap(image)
        weight = rendered.width() * rendered.height() * rendered.depth() // 8
        previous = self._previews.pop(key, None)
        if previous is not None:
            self._preview_bytes -= previous.width() * previous.height() * previous.depth() // 8
        while self._previews and self._preview_bytes + weight > self._preview_limit:
            _, removed = self._previews.popitem(last=False)
            self._preview_bytes -= removed.width() * removed.height() * removed.depth() // 8
        if weight <= self._preview_limit:
            self._previews[key] = rendered
            self._preview_bytes += weight
        self._show_pixmap(rendered, key, actual_size)

    def _show_pixmap(self, rendered: QPixmap, key: PreviewKey, actual_size: bool):
        previous = self._size
        self._size = rendered.width(), rendered.height()
        changed = (
            self._view_key is None
            or self._view_key[0] != key[0]
            or self._view_key[2] != key[2]
            or previous != self._size
        )
        leaving_actual_size = self._actual_size_default and not actual_size
        self._view_key = key
        self._actual_size_default = actual_size
        self.item.setPixmap(rendered)
        self.setSceneRect(QRectF(0, 0, *self._size))
        if changed and actual_size:
            self.actual_size()
            self.centerOn(self.item)
        elif previous != self._size or leaving_actual_size or self._fit:
            self.fit()
        self.viewport().update()

    def set_boundary(self, box: tuple[int, int, int, int] | None):
        if box is None:
            self.boundary.hide()
            return
        x1, y1, x2, y2 = box
        self.boundary.setRect(QRectF(x1, self._size[1] - y2, x2 - x1, y2 - y1))
        self.boundary.show()

    def set_checker(self, enabled: bool):
        self.checker = enabled
        self.viewport().update()

    def fit(self):
        self._fit = True
        if self._size[0]:
            self.fitInView(
                self.item.boundingRect().adjusted(-16, -16, 16, 16), Qt.AspectRatioMode.KeepAspectRatio
            )
            self.zoom_changed.emit(self.transform().m11())

    def actual_size(self):
        self._fit = False
        self.resetTransform()
        self.zoom_changed.emit(1.0)

    @override
    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.zoom_by(factor)
        event.accept()

    def zoom_by(self, factor: float):
        if 0.01 <= self.transform().m11() * factor <= 32:
            self._fit = False
            self.scale(factor, factor)
            self.zoom_changed.emit(self.transform().m11())

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._fit:
            self.fit()

    @override
    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange:
            pen = self.boundary.pen()
            pen.setColor(self.palette().color(QPalette.ColorRole.Link))
            self.boundary.setPen(pen)
            self.viewport().update()

    @override
    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        painter.fillRect(rect, self.palette().color(QPalette.ColorRole.Window))
        if not self._size[0] or not self.checker:
            return
        # Fixed screen-size checks remain legible at every zoom level.
        painter.save()
        visible = self.mapFromScene(self.item.boundingRect()).boundingRect()
        painter.resetTransform()
        tile = QPixmap(24, 24)
        tile.fill(self.palette().color(QPalette.ColorRole.Base))
        checker = QPainter(tile)
        checker.fillRect(0, 0, 12, 12, self.palette().color(QPalette.ColorRole.AlternateBase))
        checker.fillRect(12, 12, 12, 12, self.palette().color(QPalette.ColorRole.AlternateBase))
        checker.end()
        painter.setBrushOrigin(QPointF(visible.topLeft()))
        painter.fillRect(visible, QBrush(tile))
        painter.restore()
