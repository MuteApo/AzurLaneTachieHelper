from dataclasses import dataclass

from PIL import Image, ImageQt
from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent, QPainter, QPaintEvent, QPixmap, QWheelEvent
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
    def __init__(self, img: QPixmap, center: Vector2, preset: IconPreset):
        super().__init__()

        self.img = img
        self.center = center
        self.preset = preset
        self.pressed = False

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
            self.preset.pivot += Vector2(diff.x() / 100, diff.y() / -100)
            self.update()

    def wheelEvent(self, event: QWheelEvent):
        diff = event.angleDelta()
        self.preset.scale += diff.y() / 12000
        self.update()

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        rect = self.texrect()
        size = self.preset.tex2d * 1.25
        sub = self.img.copy(*rect)
        painter.drawPixmap(0, 0, sub.scaled(*size, mode=Qt.TransformationMode.SmoothTransformation))
        painter.drawRect(1, 1, *(size - 1))

    def texrect(self) -> tuple[float, float, float, float]:
        w, h = self.preset.tex2d / self.preset.scale
        x, y = self.center - Vector2(w, h) * self.preset.pivot
        return x, self.img.height() - y - h, w, h


class IconViewer(QDialog):
    def __init__(self, img: Image.Image, center: Vector2):
        super().__init__()
        self.setWindowTitle(self.tr("AzurLane Tachie Helper"))
        self.setWindowIcon(QPixmap("ico/cheshire.ico"))
        self.resize(750, 350)

        self.img = QPixmap.fromImage(ImageQt.ImageQt(img.transpose(Image.FLIP_TOP_BOTTOM)))
        self.center = center
        self.presets = IconPreset.default()

        layout1 = QHBoxLayout()
        layout1.addSpacing(50)
        layout1.addWidget(Icon(self.img, self.center, self.presets["squareicon"]))
        layout1.addWidget(QPushButton(self.tr("Clip"), self, clicked=self.onClickClip))
        layout1.addSpacing(50)

        layout2 = QVBoxLayout()
        layout2.addWidget(Icon(self.img, self.center, self.presets["herohrzicon"]))
        layout2.addLayout(layout1)

        layout = QHBoxLayout()
        layout.addWidget(Icon(self.img, self.center, self.presets["shipyardicon"]), 5)
        layout.addLayout(layout2, 10)

        self.setLayout(layout)

    def onClickClip(self):
        for k, v in self.presets.items():
            print(f"[INFO] {k}: {v}")
        self.accept()
