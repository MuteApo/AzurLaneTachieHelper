from PIL import Image
from PySide6.QtCore import QDir, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..Layer import Layer


class Previewer(QWidget):
    def __init__(self):
        super().__init__()

        self.lDep = QLabel()
        self.lDep.setAlignment(Qt.AlignmentFlag.AlignBaseline)
        self.lPath = QLabel()
        self.lPath.setAlignment(Qt.AlignmentFlag.AlignBaseline)

        info = QHBoxLayout()
        info.addWidget(self.lDep)
        info.addWidget(self.lPath)

        self.lImage = QLabel()
        self.lImage.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout()
        layout.addLayout(info)
        layout.addWidget(self.lImage)

        self.setLayout(layout)

    def display(self, layer: Layer):
        self.lDep.setText(layer.name)
        self.lPath.setText(QDir.toNativeSeparators(layer.file))
        img = layer.decode().transpose(Image.FLIP_TOP_BOTTOM)
        img.thumbnail((512, 512))
        self.lImage.setPixmap(img.toqpixmap())
        self.update()
