import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ..logger import logger
from ..module import AdbHelper


class TachiePuller(QDialog):
    def __init__(self, data: dict[str, list[str]]):
        super().__init__()
        self.setWindowTitle(self.tr("AzurLane Tachie Helper"))
        self.setWindowIcon(QPixmap("ico/cheshire.ico"))
        self.resize(300, 100)

        self.data = data

        self.label = QLabel("painting/")

        self.names = sorted([k.removeprefix("painting/") for k in data.keys() if not k.endswith("_tex")])
        self.combo_box = QComboBox()
        self.combo_box.addItems(self.names)
        self.combo_box.setEditable(True)
        self.combo_box.setEditText("")
        self.combo_box.setMaxVisibleItems(20)
        self.combo_box.setCompleter(QCompleter(self.names))

        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.combo_box)
        layout.addWidget(QPushButton(self.tr("Pull"), clicked=self.pull))

        self.setLayout(layout)

    def pull(self):
        logger.hr("Pull Tachie", 1)
        name = self.combo_box.currentText()
        logger.attr("Tachie", f"'{name}'")
        name_stem = name.removesuffix("_n")
        deps = self.data[f"painting/{name}"]
        icons = [f"{icon}/{name_stem}" for icon in ["shipyardicon", "squareicon", "herohrzicon"]]
        AdbHelper.pull(f"painting/{name}", *deps, *icons, target=name)
        os.rename(f"{name}/painting/{name}", f"{name}/{name}")
