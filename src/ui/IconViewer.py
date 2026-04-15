import math
from typing import Callable, Self

from PIL import Image, ImageChops, ImageOps
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import (
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from ..base import Config
from ..base.Data import IconPreset
from ..base.Layer import IconLayer
from ..base.Vector import Vector2
from ..logger import logger


def get_padding(w: int, h: int, center: Vector2, angle: float):
    max_w, max_h = 0, 0
    for x, y in [[w, 0], [w, h], [0, h]]:
        xx, yy = (Vector2(x, y) - center).rotate(-math.radians(angle)) + center
        max_w = max(max_w, xx)
        max_h = max(max_h, yy)
    return round(max_w) - w, round(max_h) - h


class Icon(QWidget):
    def __init__(
        self, img: Image.Image, ref: Image.Image, preset: IconPreset, center: Vector2, callback: Callable[[Self], None]
    ):
        super().__init__()
        self.setFixedSize(*preset.size)

        self.img = img
        bg = Image.new("RGBA", ref.size, (255, 255, 255, 0))
        ref = ImageChops.blend(ref, bg, 0.5).resize(preset.size.tuple())
        self.ref = ref.transpose(Image.Transpose.FLIP_TOP_BOTTOM).toqpixmap()
        self.preset = preset
        self.center = center
        self.set_last = callback

        self.pressed = False
        self.display = True
        self.rotate = False

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.set_last(self)
            self.prev_pos = event.globalPos()
            self.pressed = True

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.pressed = False

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.pressed:
            self.set_last(self)
            current_pos = event.globalPos()
            if self.rotate:
                w, h = self.preset.size
                center = QPoint(w / 2, h / 2)
                cur = self.mapFromGlobal(current_pos) - center
                prev = self.mapFromGlobal(self.prev_pos) - center
                self.apply(angle=self.calc_angle(cur, prev))
            else:
                diff = current_pos - self.prev_pos
                self.apply(pivot=self.calc_move(*diff.toTuple()))
            self.prev_pos = current_pos

    def wheelEvent(self, event: QWheelEvent):
        self.set_last(self)
        diff = event.angleDelta()
        self.apply(scale=diff.y() / 24000)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        match event.key():
            case Qt.Key.Key_Alt:
                self.display = False
                self.update()
            case Qt.Key.Key_Control:
                self.rotate = True
            case Qt.Key.Key_A:
                self.apply(pivot=self.calc_move(-1, 0))
            case Qt.Key.Key_D:
                self.apply(pivot=self.calc_move(1, 0))
            case Qt.Key.Key_W:
                self.apply(pivot=self.calc_move(0, -1))
            case Qt.Key.Key_S:
                self.apply(pivot=self.calc_move(0, 1))

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        match event.key():
            case Qt.Key.Key_Alt:
                self.display = True
                self.update()
            case Qt.Key.Key_Control:
                self.rotate = False

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.ref)
        x, y, w, h = self.texrect()
        center = (x + w / 2, y + h / 2)
        if self.display:
            pad_x, pad_y = get_padding(*self.img.size, center, self.preset.angle)
            sub = ImageOps.expand(self.img, border=(0, 0, pad_x, pad_y)).rotate(self.preset.angle, center=center)
            sub = sub.crop((x, y, x + w, y + h)).resize(self.preset.size)
            painter.drawPixmap(0, 0, sub.transpose(Image.Transpose.FLIP_TOP_BOTTOM).toqpixmap())
        painter.drawRect(0, 0, *(self.preset.size - 1))

    def calc_move(self, dx: float, dy: float):
        return Vector2(dx, dy).rotate(-math.radians(self.preset.angle))

    def calc_angle(self, u: QPoint, v: QPoint) -> float:
        a = Vector2(u.toTuple()).normalize()
        b = Vector2(v.toTuple()).normalize()
        return -math.degrees(math.asin(a.cross(b)))

    def texrect(self) -> tuple[float, float, float, float]:
        w, h = self.preset.size / self.preset.scale
        x, y = self.center - Vector2(w, h) * self.preset.pivot
        return x, y, w, h

    def apply(self, pivot: Vector2 = Vector2(0.0, 0.0), scale: float = 0, angle: float = 0):
        pivot = Vector2(pivot.X, -pivot.Y) / self.preset.size
        self.preset.apply(pivot, scale, angle)
        self.update()


class IconViewer(QDialog):
    def __init__(self, name: str, refs: dict[str, IconLayer], img: Image.Image, center: Vector2):
        super().__init__()
        self.setWindowTitle(self.tr("AzurLane Tachie Helper"))
        self.setWindowIcon(QPixmap("ico/cheshire.ico"))

        self.icons: dict[str, Icon] = {}
        self.presets = Config.get_presets(name)
        for k, v in self.presets.to_dict().items():
            ref = refs[k].decode() if k in refs else Image.new("RGBA", v.size.tuple())
            v.size = Vector2(ref.size)
            self.icons[k] = Icon(img, ref, v, center, self.setLast)
        self.last: Icon = None

        self.confirm = QPushButton(self.tr("Clip"), clicked=self.onClickClip)

        self._init_ui()

    def _init_ui(self):
        layout1 = QHBoxLayout()
        layout1.addWidget(self.icons["shipyardicon"])
        layout1.addWidget(self.icons["herohrzicon"])
        layout1.addWidget(self.icons["squareicon"])

        layout = QVBoxLayout()
        layout.addLayout(layout1)
        layout.addWidget(self.confirm)

        self.setLayout(layout)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in [Qt.Key.Key_Alt, Qt.Key.Key_Control]:
            for x in self.icons.values():
                x.keyPressEvent(event)
        elif self.last is not None:
            self.last.keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() in [Qt.Key.Key_Alt, Qt.Key.Key_Control]:
            for x in self.icons.values():
                x.keyReleaseEvent(event)
        elif self.last is not None:
            self.last.keyReleaseEvent(event)

    def onClickClip(self):
        for k, v in self.presets.to_dict().items():
            logger.attr(k, v)
        self.accept()

    def setLast(self, icon: Icon):
        self.last = icon
