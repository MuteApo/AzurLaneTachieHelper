import os
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..base import Config
from ..base.Layer import FaceLayer, IconLayer, Layer
from .Previewer import Previewer


def set_bold(item: QTableWidgetItem):
    font = item.font()
    font.setBold(True)
    item.setFont(font)


class BaseTable(QVBoxLayout):
    def __init__(self, preview: Previewer, label: str):
        super().__init__()
        self.preview = preview

        self.label = QLabel(label)
        self.label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.table = QTableWidget(cellClicked=self.onCellClicked)
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels([self.tr("Layers")])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.MinimumExpanding)

        self.addWidget(self.label)
        self.addWidget(self.table)

    def set_data(self):
        raise NotImplementedError

    def onCellClicked(self):
        raise NotImplementedError

    def load(self):
        raise NotImplementedError


class PaintingTable(BaseTable):
    def __init__(self, preview: Previewer):
        super().__init__(preview, self.tr("Paintings"))

    def set_data(self, layers: dict[str, Layer]):
        self.layers = layers
        self.num = len(self.layers) - 1
        self.table.setMinimumHeight((self.num + 1) * 30)
        self.table.setRowCount(self.num)
        self.index = {}
        for i, k in enumerate([x for x in layers.keys() if x != "face"]):
            self.table.setItem(i, 0, QTableWidgetItem(k))
            self.index[k] = i
        self.onCellClicked(0, 0)

    def onCellClicked(self, row: int, col: int):
        dep = os.path.basename(self.table.item(row, col).text())
        self.preview.display_painting(self.layers[dep.removesuffix("_tex")])

    def load(self, path: str):
        name, _ = os.path.splitext(os.path.basename(path))
        for k, v in self.layers.items():
            if v.name == name:
                v.load(path)
                set_bold(self.table.item(self.index[k], 0))


class PaintingfaceTable(BaseTable):
    def __init__(self, preview: Previewer):
        super().__init__(preview, self.tr("Paintingfaces"))
        self.last = None

    def set_data(self, faces: dict[str, FaceLayer], face_layer: Layer, prefered: Layer):
        self.faces = faces
        self.num = len(faces)
        self.table.setMinimumHeight((self.num + 1) * 30)
        self.table.setRowCount(self.num)
        self.index: dict[str, int] = {}

        if Config.get_face_extension(face_layer.meta.name_stem, "paintingface") is None:
            face_extension = [a - b for a, b in zip(prefered.box, face_layer.box)]
            Config.set_face_extension(face_layer.meta.name_stem, "paintingface", face_extension)

        for i, (k, v) in enumerate(faces.items()):
            v.set_data(face_layer, prefered)
            self.table.setItem(i, 0, QTableWidgetItem(f"paintingface/{k}"))
            self.index[k] = i

    def onCellClicked(self, row: int, col: int = 0):
        self.last = row
        idx = os.path.basename(self.table.item(row, col).text())
        self.preview.display_face(self.faces, idx)

    def refresh(self):
        if self.last is not None:
            self.onCellClicked(self.last)
            

    def load(self, folder: str):
        def worker(file: str):
            name, ext = os.path.splitext(file)
            if name in self.faces and ext == ".png":
                path = os.path.join(folder, file)
                self.faces[name].load_face(path)
                set_bold(self.table.item(self.index[name], 0))

        if os.path.isdir(folder):
            with ThreadPoolExecutor(max_workers=8) as executor:
                executor.map(worker, os.listdir(folder))
            self.refresh()


class IconTable(BaseTable):
    def __init__(self, preview: Previewer):
        super().__init__(preview, self.tr("Icons"))
        self.last = None

    def set_data(self, icons: dict[str, IconLayer], face_layer: Layer):
        self.icons = icons
        self.num = len(icons)
        self.table.setMinimumHeight((self.num + 1) * 30)
        self.table.setRowCount(self.num)
        self.index = {}
        for i, (k, v) in enumerate(icons.items()):
            v.set_data(face_layer)
            self.table.setItem(i, 0, QTableWidgetItem(k))
            self.index[k] = i

    def onCellClicked(self, row: int, col: int = 0):
        self.last = row
        idx = os.path.basename(self.table.item(row, col).text())
        self.preview.display_icon(self.icons[idx])

    def refresh(self):
        if self.last is not None:
            self.onCellClicked(self.last)

    def load(self, path: str):
        kind, _ = os.path.splitext(os.path.basename(path))
        if kind in self.icons:
            self.icons[kind].load_icon(path)
            set_bold(self.table.item(self.index[kind], 0))
            self.refresh()
