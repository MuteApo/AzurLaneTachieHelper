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

from ..Layer import Layer, PseudoLayer
from .Previewer import Previewer


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
        for i, k in enumerate(deps.keys()):
            self.table.setItem(i, 0, QTableWidgetItem(k))
        self.onCellClicked(0, 0)

    def get_text(self, row: int) -> str:
        return self.table.item(row, 0).text()

    def onCellClicked(self, row: int, col: int):
        dep = os.path.basename(self.table.item(row, col).text())
        self.preview.display_painting(self.layers[dep.removesuffix("_tex")])

    def load_painting(self, path: str) -> bool:
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
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.MinimumExpanding)

        self.addWidget(label)
        self.addWidget(self.table)

    def set_data(
        self, faces: dict[str, PseudoLayer], face_layer: Layer, prefered: Layer, adv_mode: bool
    ):
        self.faces = faces
        self.layer = face_layer
        self.num = len(faces)
        self.table.setRowCount(self.num)
        self.check_box: dict[str, QTableWidgetItem] = {}
        for i, (k, v) in enumerate(faces.items()):
            v.set_data(face_layer, prefered, adv_mode, True)
            item = QTableWidgetItem("")
            item.setCheckState(Qt.CheckState.Checked)
            item.setFlags(~Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(i, 0, item)
            self.table.setItem(i, 1, QTableWidgetItem(f"paintingface/{k}"))
            self.check_box[k] = item

    def get_text(self, row: int) -> str:
        return self.table.item(row, 0).text()

    def get_clip(self) -> dict[str, bool]:
        return {k: v.checkState() != Qt.CheckState.Unchecked for k, v in self.check_box.items()}

    def onCellClicked(self, row: int, col: int):
        idx = os.path.basename(self.table.item(row, col).text())
        self.preview.display_face(self.faces[idx])

    def load_face(self, path: str) -> bool:
        print("[INFO] Paintingface folder:")
        print("      ", QDir.toNativeSeparators(path))

        tasks: list[threading.Thread] = []
        files = [x for x in os.listdir(path) if x.endswith(".png")]
        files = [x for x in files if os.path.splitext(x)[0] in self.faces.keys()]
        for file in files:
            name, _ = os.path.splitext(file)
            img = QDir.toNativeSeparators(os.path.join(path, file))
            tasks += [threading.Thread(target=self.faces[name].load, args=(img,))]
            check_box = self.check_box[name]
            check_box.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            check_box.setCheckState(Qt.CheckState.Checked)

        if tasks == []:
            return False

        print("[INFO] Paintingfaces:")
        [_.start() for _ in tasks]
        [_.join() for _ in tasks]
        return True
