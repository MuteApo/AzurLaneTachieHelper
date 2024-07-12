import math
from typing import Callable

from PIL import Image, ImageChops
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import (
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from typing_extensions import Self

from ..base import IconLayer, IconPreset, Vector2
from ..logger import logger


class Icon(QWidget):
    def __init__(
        self, img: Image.Image, ref: Image.Image, preset: IconPreset, center: Vector2, callback: Callable[[Self], None]
    ):
        super().__init__()
        self.img = img
        bg = Image.new("RGBA", ref.size, (255, 255, 255, 0))
        self.ref = ImageChops.blend(ref, bg, 0.5).resize(preset.tex2d.tuple()).toqpixmap()
        self.preset = preset
        self.center = center
        self.set_last = callback

        self.pressed = False
        self.display = True
        self.rotate = False

        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.prev_pos = event.globalPos()
            self.pressed = True
            self.set_last(self)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self.pressed:
            self.pressed = False
            self.set_last(self)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self.pressed:
            return
        current_pos = event.globalPos()
        if self.rotate:
            w, h = self.preset.tex2d
            center = QPoint(w / 2, h / 2)
            cur = self.mapFromGlobal(current_pos) - center
            prev = self.mapFromGlobal(self.prev_pos) - center
            self.apply(angle=self.calc_angle(cur, prev))
        else:
            diff = current_pos - self.prev_pos
            self.apply(pivot=Vector2(diff.x(), -diff.y()))
        self.prev_pos = current_pos
        self.set_last(self)

    def wheelEvent(self, event: QWheelEvent):
        diff = event.angleDelta()
        self.apply(scale=diff.y() / 24000)
        self.set_last(self)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        fine_tune = {
            Qt.Key.Key_A: Vector2(-1, 0),
            Qt.Key.Key_D: Vector2(1, 0),
            Qt.Key.Key_W: Vector2(0, 1),
            Qt.Key.Key_S: Vector2(0, -1),
        }
        if event.key() == Qt.Key.Key_Alt:
            self.display = False
            self.update()
        elif event.key() == Qt.Key.Key_Control:
            self.rotate = True
        elif event.key() in fine_tune:
            self.apply(pivot=fine_tune[event.key()])
            self.update()

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Alt:
            self.display = True
            self.update()
        elif event.key() == Qt.Key.Key_Control:
            self.rotate = False

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.ref)
        x, y, w, h = self.texrect()
        if self.display:
            sub = self.img.rotate(self.preset.angle, center=(x + w / 2, y + h / 2))
            sub = sub.crop((x, y, x + w, y + h)).resize(self.preset.tex2d.tuple())
            painter.drawPixmap(0, 0, sub.transpose(Image.Transpose.FLIP_TOP_BOTTOM).toqpixmap())
        painter.drawRect(1, 1, *(self.preset.tex2d - 1))

    def calc_angle(self, u: QPoint, v: QPoint) -> float:
        a = Vector2(u.x(), -u.y())
        b = Vector2(v.x(), -v.y())
        return math.degrees(math.asin(a.cross(b) / a.norm() / b.norm()))

    def texrect(self) -> tuple[float, float, float, float]:
        w, h = self.preset.tex2d / self.preset.scale
        x, y = self.center - Vector2(w, h) * self.preset.pivot
        return x, y, w, h

    def apply(self, pivot: Vector2 = Vector2.zero(), scale: float = 0, angle: float = 0):
        self.preset.apply(pivot.rotate(self.preset.angle) / self.preset.tex2d, scale, angle)
        self.update()


class IconViewer(QDialog):
    def __init__(self, refs: dict[str, IconLayer], presets: dict[str, IconPreset], img: Image.Image, center: Vector2):
        super().__init__()
        self.setWindowTitle(self.tr("AzurLane Tachie Helper"))
        self.setWindowIcon(QPixmap("ico/cheshire.ico"))
        self.resize(700, 350)

        self.presets = presets
        self.icons: dict[str, Icon] = {}
        for kind in ["shipyardicon", "squareicon", "herohrzicon"]:
            if kind in refs:
                ref = refs[kind].decode().transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            else:
                ref = Image.new("RGBA", self.presets[kind].tex2d.tuple())
            self.icons[kind] = Icon(img, ref, self.presets[kind], center, self.setLast)
        self.last: Icon = None

        self._init_ui()

    def _init_ui(self):
        layout1 = QHBoxLayout()
        layout1.addWidget(self.icons["squareicon"], 5)
        layout1.addWidget(QPushButton(self.tr("Clip"), self, clicked=self.onClickClip), 10)

        layout2 = QVBoxLayout()
        layout2.addWidget(self.icons["herohrzicon"])
        layout2.addLayout(layout1)

        layout = QHBoxLayout()
        layout.addWidget(self.icons["shipyardicon"], 5)
        layout.addLayout(layout2, 10)

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
        for k, v in self.presets.items():
            logger.attr(k, v)
        self.accept()

    def setLast(self, icon: Icon):
        self.last = icon
