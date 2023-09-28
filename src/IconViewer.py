import math
from dataclasses import dataclass

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

from .Vector import Vector2


@dataclass
class IconPreset:
    sprite: Vector2
    tex2d: Vector2
    pivot: Vector2
    scale: float
    angle: float

    def __repr__(self) -> str:
        return f"<IconPreset angle={self.angle}, scale={self.scale}, pivot={self.pivot}>"

    def apply(self, pivot: Vector2, scale: float, angle: float):
        self.pivot += pivot
        self.scale += scale
        self.angle += angle

    @property
    def aspect_ratio(self):
        return self.tex2d.X / self.tex2d.Y

    @classmethod
    def default(cls) -> dict[str, Self]:
        return {
            "shipyardicon": IconPreset(Vector2(192, 256), Vector2(192, 256), Vector2(0.5, 0.7), 0.6, 0),
            "squareicon": IconPreset(Vector2(116, 116), Vector2(116, 116), Vector2(0.5, 0.6), 0.6, 0),
            "herohrzicon": IconPreset(Vector2(272, 80), Vector2(360, 80), Vector2(0.2, 0.6), 0.6, 0),
        }


class Icon(QWidget):
    def __init__(self, img: Image.Image, ref: Image.Image, preset: IconPreset, center: Vector2):
        super().__init__()

        self.img = img
        bg = Image.new("RGBA", ref.size, (255, 255, 255, 0))
        self.ref = ImageChops.blend(ref, bg, 0.5).toqpixmap()
        self.preset = preset
        self.center = center
        self.pressed = False
        self.display = True
        self.rotate = False

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.prev_pos = event.globalPos()
            self.pressed = True

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self.pressed:
            self.pressed = False

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self.pressed:
            return
        current_pos = event.globalPos()
        if self.rotate:
            w, h = self.preset.tex2d
            center = QPoint(w / 2, h / 2)
            cur = self.mapFromGlobal(current_pos) - center
            prev = self.mapFromGlobal(self.prev_pos) - center
            delta = self.calc_angle(cur, prev)
            self.apply(angle=delta)
        else:
            diff = current_pos - self.prev_pos
            delta = Vector2(diff.x(), -diff.y()).rotate(self.preset.angle)
            self.apply(pivot=delta / self.preset.tex2d)
        self.prev_pos = current_pos

    def wheelEvent(self, event: QWheelEvent):
        diff = event.angleDelta()
        self.apply(scale=diff.y() / 18000)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Alt:
            self.display = False
            self.update()
        elif event.key() == Qt.Key.Key_Control:
            self.rotate = True

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
            sub = self.img.rotate(self.preset.angle, Image.Resampling.BICUBIC, False, (x + w / 2, y + h / 2))
            sub = sub.crop((x, y, x + w, y + h)).resize(self.preset.tex2d, Image.Resampling.BICUBIC)
            painter.drawPixmap(0, 0, sub.transpose(Image.FLIP_TOP_BOTTOM).toqpixmap())
        painter.drawRect(1, 1, *(self.preset.tex2d - 1))

    def calc_angle(self, u: QPoint, v: QPoint) -> float:
        a = Vector2(u.x(), -u.y())
        b = Vector2(v.x(), -v.y())
        return math.degrees(math.asin(Vector2.cross(a, b) / a.norm() / b.norm()))

    def texrect(self) -> tuple[float, float, float, float]:
        w, h = self.preset.tex2d / self.preset.scale
        x, y = self.center - Vector2(w, h) * self.preset.pivot
        return x, y, w, h

    def apply(self, pivot: Vector2 = Vector2.zero(), scale: float = 0, angle: float = 0):
        self.preset.apply(pivot, scale, angle)
        self.update()


class IconViewer(QDialog):
    def __init__(self, refs: dict[str, Image.Image], img: Image.Image, center: Vector2):
        super().__init__()
        self.setWindowTitle(self.tr("AzurLane Tachie Helper"))
        self.setWindowIcon(QPixmap("ico/cheshire.ico"))
        self.resize(750, 350)

        self.presets = IconPreset.default()
        self.icons: dict[str, Icon] = {}
        for kind in ["shipyardicon", "squareicon", "herohrzicon"]:
            ref = refs.get(kind, Image.new("RGBA", self.presets[kind].tex2d.tuple()))
            self.icons[kind] = Icon(img, ref, self.presets[kind], center)

        layout1 = QHBoxLayout()
        layout1.addWidget(self.icons["squareicon"])
        layout1.addWidget(QPushButton(self.tr("Clip"), self, clicked=self.onClickClip))
        layout1.addSpacing(50)

        layout2 = QVBoxLayout()
        layout2.addWidget(self.icons["herohrzicon"])
        layout2.addLayout(layout1)

        layout = QHBoxLayout()
        layout.addWidget(self.icons["shipyardicon"], 5)
        layout.addLayout(layout2, 10)

        self.setLayout(layout)

    def keyPressEvent(self, event: QKeyEvent):
        for x in self.icons.values():
            x.keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        for x in self.icons.values():
            x.keyReleaseEvent(event)

    def onClickClip(self):
        for k, v in self.presets.items():
            print(f"[INFO] {k}: {v}")
        self.accept()
