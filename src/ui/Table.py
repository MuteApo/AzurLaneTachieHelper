import os
import threading

from PySide6.QtCore import QDir, Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..base import FaceLayer, IconLayer, IconPreset, Layer
from .Previewer import Previewer
from ..logger import logger

class Painting(QVBoxLayout):
    def __init__(self, preview: Previewer):
        super().__init__()
        self.preview = preview

        label = QLabel(self.tr("Dependencies"))
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.table = QTableWidget(cellClicked=self.onCellClicked)
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels([self.tr("Layers")])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.MinimumExpanding)

        self.addWidget(label)
        self.addWidget(self.table)

    def set_data(self, deps: dict[str, str], layers: dict[str, Layer]):
        self.deps = deps
        self.layers = layers
        self.num = len(self.layers) - 1
        self.table.setRowCount(self.num)
        for i, k in enumerate(layers.keys()):
            if k != "face":
                self.table.setItem(i, 0, QTableWidgetItem(k))
        self.onCellClicked(0, 0)

    def get_text(self, row: int) -> str:
        return self.table.item(row, 0).text()

    def onCellClicked(self, row: int, col: int):
        dep = os.path.basename(self.table.item(row, col).text())
        self.preview.display_painting(self.layers[dep.removesuffix("_tex")])

    def load(self, path: str) -> bool:
        for layer in self.layers.values():
            if layer.load(path):
                return True
        return False


class Paintingface(QVBoxLayout):
    def __init__(self, preview: Previewer):
        super().__init__()
        self.preview = preview

        label = QLabel(self.tr("Paintingfaces"))
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.table = QTableWidget(cellClicked=self.onCellClicked)
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels([self.tr("Clip"), self.tr("Layers")])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.MinimumExpanding)

        self.addWidget(label)
        self.addWidget(self.table)

    def set_data(self, faces: dict[str, FaceLayer], face_layer: Layer, prefered: Layer, adv_mode: bool):
        self.faces = faces
        self.layer = face_layer
        self.num = len(faces)
        self.table.setRowCount(self.num)
        self.adv_mode = adv_mode
        self.check_box: dict[str, QTableWidgetItem] = {}
        self.is_clip: dict[str, bool] = {}
        self.table.itemChanged.connect(self.onItemChanged)
        self.table.itemChanged.disconnect()
        for i, (k, v) in enumerate(faces.items()):
            v.set_data(face_layer, prefered, adv_mode, True)
            item = QTableWidgetItem("")
            item.setCheckState(Qt.CheckState.Checked)
            item.setFlags(~Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(i, 0, item)
            self.table.setItem(i, 1, QTableWidgetItem(f"paintingface/{k}"))
            self.check_box[k] = item
            self.is_clip[i] = True
        self.table.itemChanged.connect(self.onItemChanged)

    def onCellClicked(self, row: int, col: int):
        idx = os.path.basename(self.table.item(row, 1).text())
        self.preview.display_face_or_icon(self.faces[idx])

    def onItemChanged(self, item: QTableWidgetItem):
        if item.column() == 0:
            val = item.checkState() != Qt.CheckState.Unchecked
            if val != self.is_clip[item.row()]:
                self.is_clip[item.row()] = val
                idx = os.path.basename(self.table.item(item.row(), 1).text())
                self.faces[idx].update_clip(val)

    def load(self, path: str) -> bool:
        if not os.path.isdir(path):
            return False

        logger.attr("Paintingface folder", f"'{QDir.toNativeSeparators(path)}'")

        tasks: list[threading.Thread] = []
        files = [x for x in os.listdir(path) if x.endswith(".png")]
        files = [x for x in files if os.path.splitext(x)[0] in self.faces.keys()]
        for file in files:
            name, _ = os.path.splitext(file)
            img = QDir.toNativeSeparators(os.path.join(path, file))
            tasks += [threading.Thread(target=self.faces[name].load_face, args=(img,))]
            check_box = self.check_box[name]
            if self.adv_mode:
                check_box.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            check_box.setCheckState(Qt.CheckState.Checked)

        if tasks == []:
            return False

        [_.start() for _ in tasks]
        [_.join() for _ in tasks]
        return True


class Icon(QVBoxLayout):
    def __init__(self, preview: Previewer):
        super().__init__()
        self.preview = preview

        label = QLabel(self.tr("Icons"))
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.table = QTableWidget(cellClicked=self.onCellClicked)
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels([self.tr("Layers")])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.MinimumExpanding)

        self.addWidget(label)
        self.addWidget(self.table)

    def set_data(self, icons: dict[str, IconLayer], face_layer: Layer, prefered: Layer):
        self.icons = icons
        self.layer = face_layer
        self.prefered = prefered
        self.num = len(icons)
        self.table.setRowCount(self.num)
        for i, (k, v) in enumerate(icons.items()):
            v.set_data(face_layer, prefered)
            self.table.setItem(i, 0, QTableWidgetItem(k))

    def get_text(self, row: int) -> str:
        return self.table.item(row, 0).text()

    def onCellClicked(self, row: int, col: int):
        idx = os.path.basename(self.table.item(row, col).text())
        self.preview.display_face_or_icon(self.icons[idx])

    def load(self, path: str) -> bool:
        kind, _ = os.path.splitext(os.path.basename(path))
        if kind in self.icons:
            if self.icons[kind].load_icon(path, IconPreset.defaults()[kind]):
                return True
        return False
