import os

from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..Layer import Layer
from .Previewer import Previewer


class Dep(QVBoxLayout):
    def __init__(self, preview: Previewer):
        super().__init__()
        self.preview = preview

        label = QLabel(self.tr("Assetbundle Dependencies"))
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
        self.preview.display(self.layers[dep.removesuffix("_tex")])

    def load_painting(self, path: str) -> bool:
        for layer in self.layers.values():
            if layer.load(path):
                return True
        return False
