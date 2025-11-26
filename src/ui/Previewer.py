import os
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Callable

from PIL import Image, ImageOps
from PySide6.QtCore import QDir, Qt
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..base import Config
from ..base.Data import FaceModeType
from ..base.Layer import FaceLayer, IconLayer, Layer
from ..utility import exists


class SliderPanel(QWidget):
    def __init__(self):
        super().__init__()

        self.left = QSpinBox(
            prefix=self.tr("left: "), minimum=-2048, maximum=2048, singleStep=25, valueChanged=self.save_data
        )
        self.bottom = QSpinBox(
            prefix=self.tr("bottom: "), minimum=-2048, maximum=2048, singleStep=25, valueChanged=self.save_data
        )
        self.right = QSpinBox(
            prefix=self.tr("right: "), minimum=-2048, maximum=2048, singleStep=25, valueChanged=self.save_data
        )
        self.top = QSpinBox(
            prefix=self.tr("top: "), minimum=-2048, maximum=2048, singleStep=25, valueChanged=self.save_data
        )

        layout = QHBoxLayout()
        layout.addWidget(self.left)
        layout.addWidget(self.bottom)
        layout.addWidget(self.right)
        layout.addWidget(self.top)

        self.setLayout(layout)
        self.setVisible(False)

    def get_value(self) -> list[int]:
        return [self.left.value(), self.bottom.value(), self.right.value(), self.top.value()]

    def set_data(self, base_name: str, layer_name: str, cb):
        self.base_name = base_name
        self.layer_name = layer_name
        self.cb = cb
        left, bottom, right, top = Config.get_face_extension(base_name, layer_name)
        self.left.setValue(left)
        self.bottom.setValue(bottom)
        self.right.setValue(right)
        self.top.setValue(top)

    def save_data(self):
        Config.set_face_extension(self.base_name, self.layer_name, self.get_value())
        self.cb()


class Previewer(QWidget):
    def __init__(self, aEncodeTexture: QAction):
        super().__init__()
        self.aEncodeTexture = aEncodeTexture
        self.layer: Layer | FaceLayer | IconLayer = None
        self.fit: Callable[[Image.Image], Image.Image] = None

        self.lPath = QLabel()
        self.lName = QLabel()
        self.lWidth = QLabel()
        self.lHeight = QLabel()
        self.lImage = QLabel()
        self.lImage.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        self.lImage.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.slider_panel = SliderPanel()

        layout = QVBoxLayout()
        layout.addWidget(self.lPath)
        layout.addWidget(self.lName)
        layout.addWidget(self.lWidth)
        layout.addWidget(self.lHeight)
        layout.addWidget(self.lImage)
        layout.addWidget(self.slider_panel)

        self.setLayout(layout)

    def set_callback(self, *cbs: list[Callable[[str], bool]]):
        self.load_painting, self.load_face, self.load_icon = cbs

    def callback_wrapper(self, cb: Callable) -> Callable:
        def inner():
            cb()
            self.refresh()

        return inner

    def display_painting(self, layer: Layer):
        self.layer = layer
        self.fit = partial(ImageOps.contain, size=(512, 512), method=Image.Resampling.BICUBIC)
        self.lPath.setText(self.tr("Path:") + QDir.toNativeSeparators(layer.path))
        self.lName.setText(self.tr("Name: ") + layer.texture2D.m_Name)
        if Config.get_face_mode() == FaceModeType.Custom:
            self.slider_panel.setVisible(True)
            self.slider_panel.set_data(layer.meta.name_stem, layer.validName, self.callback_wrapper(layer.refresh))
        self.refresh()

    def display_face(self, layers: dict[str, FaceLayer], idx: str):
        def all_refresh():
            with ThreadPoolExecutor(max_workers=len(layers)) as executor:
                executor.map(lambda x: x.refresh(), layers.values())

        self.layer = layers[idx]
        if Config.get_face_mode() != FaceModeType.Off:
            self.fit = partial(ImageOps.contain, size=(512, 512), method=Image.Resampling.BICUBIC)
        else:
            self.fit = lambda x: x
        self.lName.setText(self.tr("Name: ") + self.layer.name)
        self.lPath.setText(self.tr("Path:") + QDir.toNativeSeparators(self.layer.path))
        if Config.get_face_mode() == FaceModeType.Custom:
            self.slider_panel.setVisible(True)
            self.slider_panel.set_data(self.layer.meta.name_stem, "paintingface", self.callback_wrapper(all_refresh))
        self.refresh()

    def display_icon(self, layer: IconLayer):
        self.layer = layer
        self.fit = lambda x: x
        self.lName.setText(self.tr("Name: ") + layer.name)
        self.lPath.setText(self.tr("Path:") + QDir.toNativeSeparators(layer.path))
        self.slider_panel.setVisible(False)
        self.refresh()

    def refresh(self):
        img = self.layer.repl if exists(self.layer.repl) else self.layer.decode()
        self.lWidth.setText(self.tr("Width: ") + str(img.size[0]))
        self.lHeight.setText(self.tr("Height: ") + str(img.size[1]))
        self.lImage.setPixmap(self.fit(img).transpose(Image.Transpose.FLIP_TOP_BOTTOM).toqpixmap())
        self.update()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.clone().accept()

    def dropEvent(self, event: QDropEvent):
        for link in [x.toLocalFile() for x in event.mimeData().urls()]:
            if os.path.isdir(link):
                self.load_face(link)
            elif link.endswith(".png"):
                if "icon" in link.lower():
                    self.load_icon(link)
                else:
                    self.load_painting(link)

        self.aEncodeTexture.setEnabled(True)
        self.refresh()
        event.accept()
