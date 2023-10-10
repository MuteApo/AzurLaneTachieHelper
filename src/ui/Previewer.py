import os
from typing import Callable

from PIL import Image
from PySide6.QtCore import QDir, Qt
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..Layer import Layer, PseudoLayer


class Previewer(QWidget):
    def __init__(self, aEncodeTexture: QAction):
        super().__init__()
        self.aEncodeTexture = aEncodeTexture

        self.lName = QLabel()
        self.lName.setAlignment(Qt.AlignmentFlag.AlignBaseline)
        self.lPath = QLabel()
        self.lPath.setAlignment(Qt.AlignmentFlag.AlignBaseline)

        info = QHBoxLayout()
        info.addWidget(self.lName)
        info.addWidget(self.lPath)

        self.lImage = QLabel()
        self.lImage.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout()
        layout.addLayout(info)
        layout.addWidget(self.lImage)

        self.setLayout(layout)

    def set_callback(
        self,
        load_painting: Callable[[str], bool],
        load_face: Callable[[str], bool],
        load_icon: Callable[[str], bool],
    ):
        self.load_painting = load_painting
        self.load_face = load_face
        self.load_icon = load_icon

    def display_painting(self, layer: Layer):
        self.layer = layer
        self.lName.setText(layer.name)
        self.lPath.setText(QDir.toNativeSeparators(layer.path))
        self.refresh()

    def display_face_or_icon(self, layer: PseudoLayer):
        self.layer = layer
        self.lName.setText("")
        self.lPath.setText("")
        self.refresh()

    def refresh(self):
        if self.layer.repl is None:
            img = self.layer.decode().copy()
        else:
            img = self.layer.repl.copy()
        img.thumbnail((512, 512))
        self.lImage.setPixmap(img.transpose(Image.FLIP_TOP_BOTTOM).toqpixmap())
        self.update()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if len(urls) == 1:
            link = urls[0].toLocalFile()
            if os.path.isdir(link):
                if self.load_face(link):
                    self.aEncodeTexture.setEnabled(True)
                    self.refresh()
                    event.accept()
                    return
        links = [x.toLocalFile() for x in urls]
        files = [x for x in links if x.endswith(".png")]
        for file in files:
            name, _ = os.path.splitext(file)
            if os.path.basename(name) in ["shipyardicon", "squareicon", "herohrzicon"]:
                if self.load_icon(file):
                    self.aEncodeTexture.setEnabled(True)
                    self.refresh()
                    event.accept()
            else:
                if self.load_painting(file):
                    self.aEncodeTexture.setEnabled(True)
                    self.refresh()
                    event.accept()
