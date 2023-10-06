from PIL import Image
from PySide6.QtCore import QDir, Qt
from PySide6.QtGui import QPaintEvent, QDropEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..Layer import Layer


class Previewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)

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

    def display(self, layer: Layer):
        self.layer = layer
        self.update()

    def paintEvent(self, event: QPaintEvent):
        if not hasattr(self, "layer"):
            return

        self.lName.setText(self.layer.name)
        self.lPath.setText(QDir.toNativeSeparators(self.layer.path))
        if self.layer.repl is None:
            img = self.layer.decode()
        else:
            img = self.layer.repl
        img.thumbnail((512, 512))
        self.lImage.setPixmap(img.transpose(Image.FLIP_TOP_BOTTOM).toqpixmap())

    def dropEvent(self, event: QDropEvent):
        links = []
        for url in event.mimeData().urls():
            links.append(str(url.toLocalFile()))
        if links[0].endswith(".png"):
            self.layer.load(links[0])
            event.accept()
