import math
from dataclasses import replace
from typing import override

from PIL import Image
from PySide6.QtCore import QCoreApplication, QEvent, QObject, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QFocusEvent,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPalette,
    QPen,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QMenu,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from domain.imaging import clip_icon, upright
from domain.model import IconPreset, default_presets
from ui.widgets.canvas import pixmap
from ui.widgets.chrome import WorkbenchDialog
from ui.widgets.controls import button, label


class CropPreview(QWidget):
    activated = Signal()
    moved = Signal(float, float)
    scaled = Signal(float)
    rotated = Signal(float)
    gesture_finished = Signal()

    def __init__(self):
        super().__init__()
        self.setMinimumSize(140, 160)
        self.image: QPixmap | None = None
        self.reference: QPixmap | None = None
        self.active = False
        self.reference_only = False
        self.view_scale: float | None = 1
        self.pan = QPointF()
        self._panning = False
        self._current_rect = QRectF()
        self._point: QPointF | None = None
        self._ratio = 1.0
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip(
            QCoreApplication.translate(
                "Dialogs",
                "Hold Alt to compare with the original portrait.",
            )
        )

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().color(QPalette.ColorRole.Window))
        if self.image is None:
            return
        image = self.image
        area = QRectF(self.rect()).adjusted(20, 20, -20, -20)
        tile = QPixmap(24, 24)
        tile.fill(self.palette().color(QPalette.ColorRole.Base))
        checker = QPainter(tile)
        checker.fillRect(0, 0, 12, 12, self.palette().color(QPalette.ColorRole.AlternateBase))
        checker.fillRect(12, 12, 12, 12, self.palette().color(QPalette.ColorRole.AlternateBase))
        checker.end()
        self._ratio = self.view_scale or min(area.width() / image.width(), area.height() / image.height())
        w, h = image.width() * self._ratio, image.height() * self._ratio
        frame = QRectF(
            area.center().x() - w / 2 + self.pan.x(), area.center().y() - h / 2 + self.pan.y(), w, h
        )
        self._current_rect = frame
        # At pixel zoom levels, nearest-neighbour display keeps the sampling grid honest.
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, self._ratio < 1)
        painter.fillRect(frame, QBrush(tile))
        if not self.reference_only and self.reference is not None:
            # Like the original tool, the reference remains a faint underlay;
            # opaque artwork stays readable, and Alt reveals the full reference.
            painter.setOpacity(0.35)
            painter.drawPixmap(frame, self.reference, QRectF(self.reference.rect()))
            painter.setOpacity(1)
        rendered = self.reference if self.reference_only and self.reference is not None else image
        painter.drawPixmap(frame, rendered, QRectF(rendered.rect()))
        painter.setPen(
            QPen(
                self.palette().color(QPalette.ColorRole.Link if self.active else QPalette.ColorRole.Mid),
                2 if self.active else 1,
            )
        )
        painter.drawRect(frame)

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.activated.emit()
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton and self._current_rect.contains(event.position())
        ):
            self._panning = event.button() == Qt.MouseButton.MiddleButton
            self._point = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    @override
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._point is not None and self.image is not None:
            previous = self._point
            delta = event.position() - self._point
            self._point = event.position()
            if self._panning:
                self.pan += delta
                self.update()
            elif event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                before = previous - self._current_rect.center()
                after = event.position() - self._current_rect.center()
                self.rotated.emit(
                    math.degrees(
                        math.atan2(
                            before.x() * after.y() - before.y() * after.x(),
                            before.x() * after.x() + before.y() * after.y(),
                        )
                    )
                )
            else:
                self.moved.emit(
                    delta.x() / self._ratio / self.image.width(),
                    -delta.y() / self._ratio / self.image.height(),
                )

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._point is not None:
            self._point = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            if not self._panning:
                self.gesture_finished.emit()
            self._panning = False

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
        steps: dict[int, tuple[int, int]] = {
            Qt.Key.Key_Left: (-1, 0),
            Qt.Key.Key_Right: (1, 0),
            Qt.Key.Key_Up: (0, 1),
            Qt.Key.Key_Down: (0, -1),
            Qt.Key.Key_A: (-1, 0),
            Qt.Key.Key_D: (1, 0),
            Qt.Key.Key_W: (0, 1),
            Qt.Key.Key_S: (0, -1),
        }
        if event.key() in steps and self.image is not None:
            self.activated.emit()
            dx, dy = steps[event.key()]
            distance = 10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
            self.moved.emit(dx * distance / self.image.width(), dy * distance / self.image.height())
            self.gesture_finished.emit()
            event.accept()
        elif event.key() == Qt.Key.Key_Space:
            self.reference_only = True
            self.update()
            event.accept()
        else:
            super().keyPressEvent(event)

    @override
    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.reference_only = False
            self.update()
            event.accept()
        else:
            super().keyReleaseEvent(event)

    @override
    def focusOutEvent(self, event: QFocusEvent) -> None:
        self.reference_only = False
        self.update()
        super().focusOutEvent(event)

    @override
    def wheelEvent(self, event: QWheelEvent) -> None:
        self.activated.emit()
        self.scaled.emit(event.angleDelta().y() / 24000)
        self.gesture_finished.emit()
        event.accept()


class CropDialog(WorkbenchDialog):
    def __init__(
        self,
        source: Image.Image,
        center: tuple[float, float],
        presets: dict[str, IconPreset],
        references: dict[str, Image.Image],
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(QCoreApplication.translate("Dialogs", "Create portraits"))
        self.resize(1000, 570)
        self.center = center
        self._preview_source = source.convert("RGBa")
        self.presets = dict(presets)
        self._reference_pixmaps = {
            key: pixmap(upright(image).resize(presets[key].size))
            for key, image in references.items()
            if key in presets
        }
        self._rendered_presets: dict[str, IconPreset] = {}
        self.history = [dict(presets)]
        self.history_index = 0
        layout = self.body
        self._crop_layout = layout
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        title_row = self.header.row
        guide = QToolButton()
        guide.setText(QCoreApplication.translate("Dialogs", "How to use"))
        guide.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(guide)
        help_widget = QWidget()
        help_grid = QGridLayout(help_widget)
        help_grid.setContentsMargins(16, 12, 16, 12)
        help_grid.setHorizontalSpacing(20)
        help_grid.setVerticalSpacing(12)
        for index, (gesture, action) in enumerate(
            [
                (
                    QCoreApplication.translate("Dialogs", "Drag"),
                    QCoreApplication.translate("Dialogs", "Move the portrait"),
                ),
                (
                    QCoreApplication.translate("Dialogs", "Mouse wheel"),
                    QCoreApplication.translate("Dialogs", "Resize the artwork"),
                ),
                (
                    QCoreApplication.translate("Dialogs", "Ctrl + drag"),
                    QCoreApplication.translate("Dialogs", "Rotate the artwork"),
                ),
                ("Alt", QCoreApplication.translate("Dialogs", "Hold to compare originals")),
                ("WASD / ← ↑ ↓ →", QCoreApplication.translate("Dialogs", "Move 1 pixel (Shift: 10)")),
                (
                    QCoreApplication.translate("Dialogs", "Middle-drag"),
                    QCoreApplication.translate("Dialogs", "Pan a zoomed view"),
                ),
            ]
        ):
            help_grid.addWidget(label(gesture, "heading"), index, 0)
            help_grid.addWidget(label(action, ""), index, 1)
        help_action = QWidgetAction(menu)
        help_action.setDefaultWidget(help_widget)
        menu.addAction(help_action)
        guide.setMenu(menu)
        title_row.addWidget(guide)
        layout.addWidget(
            label(
                QCoreApplication.translate(
                    "Dialogs",
                    "Drag a portrait to position it. Use the wheel to adjust its size.",
                ),
                "",
            )
        )
        row = QHBoxLayout()
        titles = [
            ("shipyardicon", QCoreApplication.translate("Dialogs", "Dock portrait")),
            ("herohrzicon", QCoreApplication.translate("Dialogs", "Wide portrait")),
            ("squareicon", QCoreApplication.translate("Dialogs", "Square portrait")),
        ]
        self.previews: dict[str, CropPreview] = {}
        for key, title in titles:
            preview = CropPreview()
            width, height = presets[key].size
            preview.setMinimumSize(width + 40, height + 40)
            preview.reference = self._reference_pixmaps.get(key)
            column = QVBoxLayout()
            heading = label(title, "heading")
            heading.setToolTip(f"{width} × {height} px")
            heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
            column.addWidget(heading)
            column.addWidget(preview, 1)
            row.addLayout(column, width)
            self.previews[key] = preview
        self.preview = self.previews["shipyardicon"]
        layout.addLayout(row, 1)
        view_tools = QHBoxLayout()
        view_tools.addWidget(label(QCoreApplication.translate("Dialogs", "View zoom")))
        self.view_zoom = QComboBox()
        self.view_zoom.addItem(QCoreApplication.translate("Dialogs", "Fit"), None)
        for factor in (1, 2, 4, 8):
            self.view_zoom.addItem(f"{factor * 100}%", factor)
        self.view_zoom.setCurrentIndex(1)
        self.view_zoom.currentIndexChanged.connect(self._view_zoom)
        view_tools.addWidget(self.view_zoom)
        view_tools.addStretch()
        self.precision_toggle = QToolButton()
        self.precision_toggle.setText(QCoreApplication.translate("Dialogs", "Precise adjustments"))
        self.precision_toggle.setCheckable(True)
        self.precision_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.precision_toggle.setArrowType(Qt.ArrowType.RightArrow)
        view_tools.addWidget(self.precision_toggle)
        layout.addLayout(view_tools)
        self.precision = QWidget()
        advanced_columns = QHBoxLayout(self.precision)
        advanced_columns.setContentsMargins(0, 0, 0, 0)
        advanced_columns.setSpacing(24)
        right = QVBoxLayout()
        self.kind = QComboBox()
        for key, title in titles:
            width, height = self.presets[key].size
            self.kind.addItem(f"{title} · {width} × {height}", key)
        right.addWidget(self.kind)
        form = QGridLayout()
        self.values: dict[str, QDoubleSpinBox] = {}
        for index, (key, title, low, high, step) in enumerate(
            [
                ("x", QCoreApplication.translate("Dialogs", "Horizontal / px"), -100000, 100000, 1),
                ("y", QCoreApplication.translate("Dialogs", "Vertical / px"), -100000, 100000, 1),
                ("scale", QCoreApplication.translate("Dialogs", "Scale"), 0.01, 100, 0.001),
                ("angle", QCoreApplication.translate("Dialogs", "Rotation / °"), -360, 360, 0.1),
            ]
        ):
            field = QDoubleSpinBox()
            field.setRange(low, high)
            field.setDecimals(4 if key == "scale" else 2)
            field.setSingleStep(step)
            field.setKeyboardTracking(False)
            field.valueChanged.connect(self._numbers)
            field.editingFinished.connect(self._remember)
            self.values[key] = field
            form.addWidget(label(title), index // 2 * 2, index % 2)
            form.addWidget(field, index // 2 * 2 + 1, index % 2)
        right.addLayout(form)
        history_row = QHBoxLayout()
        self.undo_button = button(QCoreApplication.translate("Dialogs", "Undo"), self._undo)
        self.redo_button = button(QCoreApplication.translate("Dialogs", "Redo"), self._redo)
        history_row.addWidget(self.undo_button)
        history_row.addWidget(self.redo_button)
        history_row.addWidget(
            button(QCoreApplication.translate("Dialogs", "Reset this portrait"), self._reset)
        )
        history_row.addStretch()
        right.addStretch()
        advanced_columns.addLayout(right, 1)
        layout.addWidget(self.precision)
        self.precision.hide()
        self.precision_toggle.toggled.connect(self._show_precision)
        # Keep common actions on the same strip as the view controls.
        view_tools.insertLayout(2, history_row)
        self.save_files = QCheckBox(QCoreApplication.translate("Dialogs", "Also save images to a folder"))
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName("primary")
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(
            QCoreApplication.translate("Dialogs", "Apply portraits")
        )
        self.save_files.toggled.connect(
            lambda checked: buttons.button(QDialogButtonBox.StandardButton.Save).setText(
                QCoreApplication.translate("Dialogs", "Apply and save…")
                if checked
                else QCoreApplication.translate("Dialogs", "Apply portraits")
            )
        )
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            QCoreApplication.translate("Dialogs", "Cancel")
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        footer = QHBoxLayout()
        footer.addWidget(self.save_files)
        footer.addStretch()
        footer.addWidget(buttons)
        layout.addLayout(footer)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._render)
        self.kind.currentIndexChanged.connect(self._load)
        for key, preview in self.previews.items():
            preview.activated.connect(lambda key=key: self.kind.setCurrentIndex(self.kind.findData(key)))
            preview.moved.connect(self._move)
            preview.scaled.connect(self._scale)
            preview.rotated.connect(self._rotate)
            preview.gesture_finished.connect(self._remember)
        for widget in [self, *self.findChildren(QWidget)]:
            widget.installEventFilter(self)
        self._load()

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if isinstance(event, QKeyEvent) and event.key() == Qt.Key.Key_Alt:
            if not event.isAutoRepeat():
                self._peek(event.type() == QEvent.Type.KeyPress)
            return True
        if watched is self and event.type() == QEvent.Type.WindowDeactivate:
            self._peek(False)
        return super().eventFilter(watched, event)

    def _show_precision(self, expanded: bool):
        self.precision.setVisible(expanded)
        self.precision_toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self._crop_layout.activate()
        self.resize(self.width(), self.sizeHint().height())

    def _load(self):
        self.timer.stop()
        self.preview = self.previews[self.kind.currentData()]
        for preview in self.previews.values():
            preview.active = preview is self.preview
            preview.update()
        self._sync_values()
        self.view_zoom.blockSignals(True)
        self.view_zoom.setCurrentIndex(self.view_zoom.findData(self.preview.view_scale))
        self.view_zoom.blockSignals(False)
        self._render()
        self._history_buttons()

    def _sync_values(self):
        preset = self.presets[self.kind.currentData()]
        angle = math.radians(preset.angle)
        dx, dy = (preset.pivot[0] - 0.5) * preset.size[0], (preset.pivot[1] - 0.5) * preset.size[1]
        # User-facing offsets are output pixels: positive right/down, even after rotation.
        x = math.cos(angle) * dx + math.sin(angle) * dy
        y = math.sin(angle) * dx - math.cos(angle) * dy
        for key, value in zip(("x", "y", "scale", "angle"), (x, y, preset.scale, preset.angle)):
            self.values[key].blockSignals(True)
            self.values[key].setValue(value)
            self.values[key].blockSignals(False)

    def _numbers(self):
        key = self.kind.currentData()
        angle = math.radians(self.values["angle"].value())
        x, y = self.values["x"].value(), -self.values["y"].value()
        width, height = self.presets[key].size
        self.presets[key] = replace(
            self.presets[key],
            pivot=(
                0.5 + (math.cos(angle) * x - math.sin(angle) * y) / width,
                0.5 + (math.sin(angle) * x + math.cos(angle) * y) / height,
            ),
            scale=self.values["scale"].value(),
            angle=self.values["angle"].value(),
        )
        self._schedule_render()

    def _schedule_render(self):
        # Throttle, rather than debounce: continuous dragging must keep drawing.
        if not self.timer.isActive():
            self.timer.start()

    def _move(self, dx, dy):
        # A drag is in output-frame coordinates; pivot lives in the rotated source frame.
        preset = self.presets[self.kind.currentData()]
        angle = math.radians(preset.angle)
        x, y = dx * preset.size[0], dy * preset.size[1]
        delta_x = (math.cos(angle) * x - math.sin(angle) * y) / preset.size[0]
        delta_y = (math.sin(angle) * x + math.cos(angle) * y) / preset.size[1]
        self.presets[self.kind.currentData()] = replace(
            preset, pivot=(preset.pivot[0] + delta_x, preset.pivot[1] + delta_y)
        )
        self._sync_values()
        self._schedule_render()

    def _scale(self, delta):
        self.values["scale"].setValue(self.values["scale"].value() + delta)

    def _rotate(self, degrees):
        key = self.kind.currentData()
        preset = self.presets[key]
        self.presets[key] = replace(preset, angle=(preset.angle + degrees + 180) % 360 - 180)
        self._sync_values()
        self._schedule_render()

    def _render(self):
        for key, preview in self.previews.items():
            if self._rendered_presets.get(key) == self.presets[key]:
                continue
            image = upright(
                clip_icon(self._preview_source, self.center, self.presets[key], shadow=key == "shipyardicon")
            )
            preview.image = pixmap(image)
            self._rendered_presets[key] = self.presets[key]
            preview.update()

    def _view_zoom(self):
        self.preview.view_scale = self.view_zoom.currentData()
        self.preview.pan = QPointF()
        self.preview.update()

    def _peek(self, active: bool):
        for preview in self.previews.values():
            preview.reference_only = active and preview.reference is not None
            preview.update()

    def _remember(self):
        if self.history[self.history_index] != self.presets:
            self.history = self.history[: self.history_index + 1] + [dict(self.presets)]
            self.history_index += 1
        self._history_buttons()

    def _history_buttons(self):
        self.undo_button.setEnabled(self.history_index > 0)
        self.redo_button.setEnabled(self.history_index < len(self.history) - 1)

    def _undo(self):
        self._remember()
        if self.history_index > 0:
            self.history_index -= 1
            self.presets = dict(self.history[self.history_index])
            self._load()

    def _redo(self):
        if self.history_index + 1 < len(self.history):
            self.history_index += 1
            self.presets = dict(self.history[self.history_index])
            self._load()

    def _reset(self):
        key = self.kind.currentData()
        self.presets[key] = replace(default_presets()[key], size=self.presets[key].size)
        self._remember()
        self._load()
