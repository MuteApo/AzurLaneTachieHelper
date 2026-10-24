"""Interactive placement of replacement images whose canvas dimensions differ."""

from dataclasses import replace
from typing import override

from PySide6.QtCore import QCoreApplication, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
    QResizeEvent,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QSlider,
    QVBoxLayout,
)

from application.session import ImportImage
from domain.model import ImageAlignment
from ui.widgets.canvas import pixmap
from ui.widgets.chrome import WorkbenchDialog
from ui.widgets.controls import button, label


class AlignmentView(QGraphicsView):
    moved = Signal(float, float)

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setMinimumSize(420, 340)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        pen = QPen(self.palette().color(QPalette.ColorRole.Mid))
        pen.setCosmetic(True)
        self.frame = self.scene().addRect(QRectF(), pen)
        self.frame.setFlag(QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape)
        self.reference = QGraphicsPixmapItem(self.frame)
        self.overlay = QGraphicsPixmapItem(self.frame)
        self.overlay.setOpacity(0.65)
        border = QPen(self.palette().color(QPalette.ColorRole.Link), 1, Qt.PenStyle.DashLine)
        border.setCosmetic(True)
        self.outline = self.scene().addRect(QRectF(), border)
        self._point: QPointF | None = None
        self._panning = False
        self._remainder = QPointF()
        self._fit = True
        self.item_data: ImportImage | None = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def load(self, item: ImportImage, alignment: ImageAlignment):
        self.item_data = item
        assert item.preview is not None and item.reference is not None
        self.frame.setRect(QRectF(0, 0, *item.canvas_size))
        self.setSceneRect(self.frame.rect())
        reference = pixmap(item.reference)
        self.reference.setPixmap(reference)
        self.reference.setTransform(
            QTransform.fromScale(
                item.canvas_size[0] / reference.width(), item.canvas_size[1] / reference.height()
            )
        )
        self.overlay.setPixmap(pixmap(item.preview))
        self.place(alignment)
        self.fit()

    def place(self, alignment: ImageAlignment):
        item = self.item_data
        if item is None:
            return
        preview = self.overlay.pixmap()
        self.overlay.setTransform(
            QTransform.fromScale(
                item.size[0] * alignment.scale / preview.width(),
                item.size[1] * alignment.scale / preview.height(),
            )
        )
        self.overlay.setPos(alignment.x, alignment.y)
        self.outline.setRect(
            QRectF(alignment.x, alignment.y, item.size[0] * alignment.scale, item.size[1] * alignment.scale)
        )

    def fit(self):
        self._fit = True
        self.fitInView(self.frame.rect().adjusted(-16, -16, 16, 16), Qt.AspectRatioMode.KeepAspectRatio)

    def actual_size(self):
        self._fit = False
        self.resetTransform()

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._fit:
            self.fit()

    @override
    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = 1.15 ** (event.angleDelta().y() / 120)
        if 0.01 <= self.transform().m11() * factor <= 32:
            self._fit = False
            self.scale(factor, factor)
        event.accept()

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
            self.setFocus()
            self._point = event.position()
            self._remainder = QPointF()
            self._panning = event.button() == Qt.MouseButton.MiddleButton
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    @override
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._point is None:
            return
        if self._panning:
            delta = event.position() - self._point
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - round(delta.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - round(delta.y()))
        else:
            delta = self.mapToScene(event.position().toPoint()) - self.mapToScene(self._point.toPoint())
            self._remainder += delta
            x, y = round(self._remainder.x()), round(self._remainder.y())
            self._remainder -= QPointF(x, y)
            self.moved.emit(x, y)
        self._point = event.position()

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._point = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
        steps: dict[int, tuple[int, int]] = {
            Qt.Key.Key_Left: (-1, 0),
            Qt.Key.Key_Right: (1, 0),
            Qt.Key.Key_Up: (0, -1),
            Qt.Key.Key_Down: (0, 1),
        }
        if event.key() in steps:
            x, y = steps[event.key()]
            step = 10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
            self.moved.emit(x * step, y * step)
            event.accept()
        else:
            super().keyPressEvent(event)

    @override
    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        painter.fillRect(rect, self.palette().color(QPalette.ColorRole.Window))
        visible = self.mapFromScene(self.frame.rect()).boundingRect()
        painter.save()
        painter.resetTransform()
        tile = QPixmap(24, 24)
        tile.fill(self.palette().color(QPalette.ColorRole.Base))
        checker = QPainter(tile)
        for x, y in ((0, 0), (12, 12)):
            checker.fillRect(x, y, 12, 12, self.palette().color(QPalette.ColorRole.AlternateBase))
        checker.end()
        painter.fillRect(visible, QBrush(tile))
        painter.restore()


class AlignmentDialog(WorkbenchDialog):
    def __init__(self, items: list[ImportImage], parent=None):
        super().__init__(parent)
        self.items = items
        self.alignments = {item.key: self.centered(item) for item in items}
        self.setWindowTitle(QCoreApplication.translate("Alignment", "Align replacement images"))
        self.resize(1040, 690)
        layout = self.body
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        note = label(
            QCoreApplication.translate(
                "Alignment", "The image size differs. Drag to align it with the artwork underneath."
            ),
            "",
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.files = QComboBox()
        for item in items:
            self.files.addItem(item.source.name)
        layout.addWidget(self.files)
        body = QHBoxLayout()
        body.setSpacing(20)
        self.view = AlignmentView()
        body.addWidget(self.view, 1)
        controls = QVBoxLayout()
        controls.setSpacing(12)
        self.dimensions = label("")
        self.dimensions.setWordWrap(True)
        self.dimensions.setMaximumWidth(230)
        controls.addWidget(self.dimensions)
        form = QFormLayout()
        self.offset_x = QDoubleSpinBox()
        self.offset_y = QDoubleSpinBox()
        self.scale = QDoubleSpinBox()
        for field in (self.offset_x, self.offset_y):
            field.setRange(-100000, 100000)
            field.setDecimals(0)
            field.setSuffix(" px")
        self.scale.setRange(0.01, 10000)
        self.scale.setDecimals(2)
        self.scale.setSuffix(" %")
        self.scale.setSingleStep(1)
        for field in (self.offset_x, self.offset_y, self.scale):
            field.setKeyboardTracking(False)
            field.valueChanged.connect(self._numbers)
        form.addRow(QCoreApplication.translate("Alignment", "Left"), self.offset_x)
        form.addRow(QCoreApplication.translate("Alignment", "Top"), self.offset_y)
        form.addRow(QCoreApplication.translate("Alignment", "Image scale"), self.scale)
        controls.addLayout(form)
        controls.addWidget(
            button(QCoreApplication.translate("Alignment", "Original size, centered"), self._reset)
        )
        controls.addWidget(
            button(QCoreApplication.translate("Alignment", "Fit image to canvas"), self._fit_image)
        )
        controls.addWidget(label(QCoreApplication.translate("Alignment", "Image opacity"), ""))
        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(0, 100)
        self.opacity.setValue(65)
        self.opacity.valueChanged.connect(lambda value: self.view.overlay.setOpacity(value / 100))
        controls.addWidget(self.opacity)
        reference = QCheckBox(QCoreApplication.translate("Alignment", "Show reference artwork"))
        reference.setChecked(True)
        reference.toggled.connect(self.view.reference.setVisible)
        controls.addWidget(reference)
        controls.addStretch()
        hint = label(
            QCoreApplication.translate(
                "Alignment", "Wheel: zoom view · Middle drag: pan\nArrow keys: move 1 px · Shift: 10 px"
            )
        )
        hint.setWordWrap(True)
        hint.setMaximumWidth(230)
        controls.addWidget(hint)
        zoom = QHBoxLayout()
        zoom.addWidget(button(QCoreApplication.translate("Alignment", "Fit view"), self.view.fit))
        zoom.addWidget(button("100%", self.view.actual_size))
        controls.addLayout(zoom)
        body.addLayout(controls)
        layout.addLayout(body, 1)
        self.shared = QCheckBox(
            QCoreApplication.translate("Alignment", "Use this alignment for images of the same size")
        )
        self.shared.setChecked(True)
        self.shared.toggled.connect(self._share)
        layout.addWidget(self.shared)
        self.warning = label(
            QCoreApplication.translate("Alignment", "Move the image onto the canvas to continue.")
        )
        layout.addWidget(self.warning)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.apply_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.apply_button.setObjectName("primary")
        self.apply_button.setText(QCoreApplication.translate("Alignment", "Align and import"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.view.moved.connect(self._move)
        self.files.currentIndexChanged.connect(self._load)
        self._load()

    @staticmethod
    def centered(item: ImportImage, scale: float = 1) -> ImageAlignment:
        return ImageAlignment(
            round((item.canvas_size[0] - item.size[0] * scale) / 2),
            round((item.canvas_size[1] - item.size[1] * scale) / 2),
            scale,
        )

    def _load(self):
        item = self.items[self.files.currentIndex()]
        self.dimensions.setText(
            QCoreApplication.translate("Alignment", "Image: {0} × {1}\nCanvas: {2} × {3}").format(
                *item.size, *item.canvas_size
            )
        )
        self.shared.setVisible(
            sum(other.size == item.size and other.canvas_size == item.canvas_size for other in self.items) > 1
        )
        self.view.load(item, self.alignments[item.key])
        self._sync()

    def _sync(self):
        item = self.items[self.files.currentIndex()]
        value = self.alignments[item.key]
        for field, number in (
            (self.offset_x, value.x),
            (self.offset_y, value.y),
            (self.scale, value.scale * 100),
        ):
            field.blockSignals(True)
            field.setValue(number)
            field.blockSignals(False)
        self.view.place(value)
        valid = all(self._overlaps(other, self.alignments[other.key]) for other in self.items)
        self.apply_button.setEnabled(valid)
        self.warning.setVisible(not valid)

    @staticmethod
    def _overlaps(item: ImportImage, value: ImageAlignment) -> bool:
        return (
            value.x < item.canvas_size[0]
            and value.y < item.canvas_size[1]
            and value.x + item.size[0] * value.scale > 0
            and value.y + item.size[1] * value.scale > 0
        )

    def _set(self, value: ImageAlignment):
        item = self.items[self.files.currentIndex()]
        self.alignments[item.key] = value
        if self.shared.isChecked():
            for other in self.items:
                if (other.size, other.canvas_size) == (item.size, item.canvas_size):
                    self.alignments[other.key] = value
        self._sync()

    def _share(self, checked: bool):
        if checked:
            self._set(self.alignments[self.items[self.files.currentIndex()].key])

    def _numbers(self):
        self._set(ImageAlignment(self.offset_x.value(), self.offset_y.value(), self.scale.value() / 100))

    def _move(self, x: float, y: float):
        value = self.alignments[self.items[self.files.currentIndex()].key]
        self._set(replace(value, x=round(value.x + x), y=round(value.y + y)))

    def _reset(self):
        self._set(self.centered(self.items[self.files.currentIndex()]))

    def _fit_image(self):
        item = self.items[self.files.currentIndex()]
        self._set(self.centered(item, min(a / b for a, b in zip(item.canvas_size, item.size))))

    @override
    def accept(self) -> None:
        if self.apply_button.isEnabled():
            super().accept()
