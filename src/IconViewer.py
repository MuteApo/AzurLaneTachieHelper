from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageQt
from PySide6.QtCore import Qt
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

    def __repr__(self) -> str:
        return f"<IconPreset scale={self.scale}, pivot={self.pivot}>"

    @classmethod
    def default(cls) -> dict[str, Self]:
        return {
            "shipyardicon": IconPreset(
                Vector2(192, 256),
                Vector2(192, 256),
                Vector2(0.5, 0.7),
                0.6,
            ),
            "squareicon": IconPreset(
                Vector2(116, 116),
                Vector2(116, 116),
                Vector2(0.5, 0.6),
                0.6,
            ),
            "herohrzicon": IconPreset(
                Vector2(272, 80),
                Vector2(360, 80),
                Vector2(0.2, 0.6),
                0.6,
            ),
        }


class Icon(QWidget):
    def __init__(self, img: Image.Image, ref: Image.Image, preset: IconPreset, center: Vector2):
        super().__init__()

        self.img = QPixmap.fromImage(ImageQt.ImageQt(img.transpose(Image.FLIP_TOP_BOTTOM)))
        data = np.array(ref)
        data[..., 3] //= 2
        self.ref = QPixmap.fromImage(ImageQt.ImageQt(Image.fromarray(data)))
        self.preset = preset
        self.center = center
        self.pressed = False
        self.display = True

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.prev_pos = event.globalPos()
            self.pressed = True

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self.pressed:
            self.pressed = False

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.pressed:
            current_pos = event.globalPos()
            diff = current_pos - self.prev_pos
            self.prev_pos = current_pos
            self.preset.pivot += Vector2(diff.x() / 300, diff.y() / -300)
            if self.check(self.preset):
                self.update()
            else:
                self.preset.pivot -= Vector2(diff.x() / 300, diff.y() / -300)

    def wheelEvent(self, event: QWheelEvent):
        diff = event.angleDelta()
        self.preset.scale += diff.y() / 18000
        if self.check(self.preset):
            self.update()
        else:
            self.preset.scale -= diff.y() / 18000

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.ref)
        rect = self.texrect(self.preset)
        size = self.preset.tex2d
        if self.display:
            sub = self.img.copy(*rect).scaled(
                *size, mode=Qt.TransformationMode.SmoothTransformation
            )
            painter.drawPixmap(0, 0, sub)
        painter.drawRect(1, 1, *(size - 1))

    def texrect(self, preset: IconPreset) -> tuple[float, float, float, float]:
        w, h = preset.tex2d / preset.scale
        x, y = self.center - Vector2(w, h) * preset.pivot
        return x, self.img.height() - y - h, w, h

    def check(self, preset: IconPreset) -> bool:
        x, y, w, h = self.texrect(preset)
        return x > 0 and y > 0 and x + w < self.img.width() and y + h < self.img.height()


class IconViewer(QDialog):
    def __init__(self, refs: dict[str, Image.Image], img: Image.Image, center: Vector2):
        super().__init__()
        self.setWindowTitle(self.tr("AzurLane Tachie Helper"))
        self.setWindowIcon(QPixmap("ico/cheshire.ico"))
        self.resize(750, 350)

        self.presets = IconPreset.default()
        self.shipyardicon = Icon(img, refs["squareicon"], self.presets["squareicon"], center)
        self.squareicon = Icon(img, refs["shipyardicon"], self.presets["shipyardicon"], center)
        self.herohrzicon = Icon(img, refs["herohrzicon"], self.presets["herohrzicon"], center)

        layout1 = QHBoxLayout()
        layout1.addSpacing(50)
        layout1.addWidget(self.shipyardicon)
        layout1.addWidget(QPushButton(self.tr("Clip"), self, clicked=self.onClickClip))
        layout1.addSpacing(50)

        layout2 = QVBoxLayout()
        layout2.addWidget(self.herohrzicon)
        layout2.addLayout(layout1)

        layout = QHBoxLayout()
        layout.addWidget(self.squareicon, 5)
        layout.addLayout(layout2, 10)

        self.setLayout(layout)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Alt:
            self.shipyardicon.display = False
            self.squareicon.display = False
            self.herohrzicon.display = False
            self.update()

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Alt:
            self.shipyardicon.display = True
            self.squareicon.display = True
            self.herohrzicon.display = True
            self.update()

    def onClickClip(self):
        for k, v in self.presets.items():
            print(f"[INFO] {k}: {v}")
        self.accept()
