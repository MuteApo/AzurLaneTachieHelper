from typing import Callable, Self

from PIL import Image, ImageChops
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent, QPainter, QPaintEvent, QPixmap, QWheelEvent
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from ..base import Config, IconLayer, IconPreset, Vector2
from ..logger import logger


class Icon(QWidget):
    def __init__(
        self, img: Image.Image, ref: Image.Image, preset: IconPreset, center: Vector2, callback: Callable[[Self], None]
    ):
        super().__init__()
        self.setFixedSize(*preset.tex2d)

        self.img = img
        ref = ref.transpose(Image.Transpose.FLIP_TOP_BOTTOM).resize(preset.tex2d)
        bg = Image.new("RGBA", preset.tex2d.tuple(), (255, 255, 255, 0))
        self.ref = ImageChops.blend(ref, bg, 0.5).toqpixmap()
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
            diff = current_pos - self.prev_pos
            self.prev_pos = current_pos
            self.apply(pivot=Vector2(diff.x(), -diff.y()))

    def wheelEvent(self, event: QWheelEvent):
        self.set_last(self)
        diff = event.angleDelta()
        if self.rotate:
            self.apply(angle=-diff.y() / 600)
        else:
            self.apply(scale=diff.y() / 36000)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        match event.key():
            case Qt.Key.Key_Alt:
                self.display = False
                self.update()
            case Qt.Key.Key_Control:
                self.rotate = True
            case Qt.Key.Key_A:
                self.apply(pivot=Vector2(-1, 0))
            case Qt.Key.Key_D:
                self.apply(pivot=Vector2(1, 0))
            case Qt.Key.Key_W:
                self.apply(pivot=Vector2(0, 1))
            case Qt.Key.Key_S:
                self.apply(pivot=Vector2(0, -1))

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        match event.key():
            case Qt.Key.Key_Alt:
                self.display = True
            case Qt.Key.Key_Control:
                self.rotate = False
        self.update()

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.ref)
        x, y, w, h = self.texrect()
        if self.display:
            sub = self.img.rotate(self.preset.angle, center=(x + w / 2, y + h / 2))
            sub = sub.crop((x, y, x + w, y + h)).resize(self.preset.tex2d)
            painter.drawPixmap(0, 0, sub.transpose(Image.Transpose.FLIP_TOP_BOTTOM).toqpixmap())
        painter.drawRect(0, 0, *(self.preset.tex2d - 1))

    def texrect(self) -> tuple[float, float, float, float]:
        w, h = self.preset.tex2d / self.preset.scale
        x, y = self.center - Vector2(w, h) * self.preset.pivot
        return x, y, w, h

    def apply(self, pivot: Vector2 = Vector2(0), scale: float = 0, angle: float = 0):
        self.preset.apply(pivot / self.preset.tex2d, scale, angle)
        self.update()


class IconViewer(QDialog):
    def __init__(self, name: str, refs: dict[str, IconLayer], img: Image.Image, center: Vector2):
        super().__init__()
        self.setWindowTitle(self.tr("AzurLane Tachie Helper"))
        self.setWindowIcon(QPixmap("ico/cheshire.ico"))

        self.presets = Config.get_presets(name)
        self.icons: dict[str, Icon] = {}
        for kind in ["shipyardicon", "herohrzicon", "squareicon"]:
            ref = refs[kind].decode if kind in refs else Image.new("RGBA", self.presets[kind].tex2d.tuple())
            self.icons[kind] = Icon(img, ref, self.presets[kind], center, self.setLast)
        self.last: Icon = None

        self.confirm = QPushButton(self.tr("Clip"), clicked=self.onClickClip)

        self.translation = QLabel(self.tr("Translation: WASD or drag muouse with left button"))
        self.translation.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        self.translation.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.scale = QLabel(self.tr("Scale: scroll mouse wheel"))
        self.scale.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        self.scale.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.rotation = QLabel(self.tr("Rotation: Hold Ctrl and scroll mouse wheel"))
        self.rotation.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        self.rotation.setAlignment(Qt.AlignmentFlag.AlignRight)

        self._init_ui()

    def _init_ui(self):
        layout1 = QHBoxLayout()
        layout1.addWidget(self.translation)
        layout1.addWidget(self.scale)
        layout1.addWidget(self.rotation)

        layout2 = QHBoxLayout()
        layout2.addWidget(self.icons["shipyardicon"])
        layout2.addWidget(self.icons["herohrzicon"])
        layout2.addWidget(self.icons["squareicon"])

        layout = QVBoxLayout()
        layout.addLayout(layout1)
        layout.addLayout(layout2)
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
        for k, v in self.presets.items():
            logger.attr(k, v)
        self.accept()

    def setLast(self, icon: Icon):
        self.last = icon
