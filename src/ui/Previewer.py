import os
from typing import Callable

from PIL import Image
from PySide6.QtCore import QDir, Qt
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..base import FaceLayer, IconLayer, Layer
from ..utility import exists


class Previewer(QWidget):
    def __init__(self, aEncodeTexture: QAction):
        super().__init__()
        self.aEncodeTexture = aEncodeTexture

        self.lName = QLabel()
        self.lPath = QLabel()
        self.lImage = QLabel()

        info = QHBoxLayout()
        info.addWidget(self.lName)
        info.addWidget(self.lPath)

        layout = QVBoxLayout()
        layout.addLayout(info)
        layout.addWidget(self.lImage, stretch=1, alignment=Qt.AlignmentFlag.AlignCenter)

        self.setLayout(layout)

    def set_callback(self, *cbs: list[Callable[[str], bool]]):
        self.load_painting, self.load_face, self.load_icon = cbs

    def display_painting(self, layer: Layer):
        self.layer = layer
        self.lName.setText(layer.texture2D.name)
        self.lPath.setText(QDir.toNativeSeparators(layer.path))
        self.refresh()

    def display_face_or_icon(self, layer: FaceLayer | IconLayer):
        self.layer = layer
        self.lName.setText(layer.name)
        self.lPath.setText(QDir.toNativeSeparators(layer.path))
        self.refresh()

    def refresh(self):
        if not exists(self.layer.repl):
            self.layer.repl = self.layer.decode()
        img = self.layer.repl.copy()
        img.thumbnail((512, 512))
        self.lImage.setPixmap(img.transpose(Image.Transpose.FLIP_TOP_BOTTOM).toqpixmap())
        self.update()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.clone().accept()

    def dropEvent(self, event: QDropEvent):
        flag = False
        for link in [x.toLocalFile() for x in event.mimeData().urls()]:
            if os.path.isdir(link) and self.load_face(link):
                flag = True
            elif link.endswith(".png"):
                if self.load_icon(link) or self.load_painting(link):
                    flag = True
        if flag:
            self.aEncodeTexture.setEnabled(True)
            self.refresh()
            event.accept()
