import os

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
)

from ..logger import logger
from ..module import AdbHelper


class TachiePuller(QDialog):
    def __init__(self, data: dict[str, list[str]]):
        super().__init__()
        self.setWindowTitle(self.tr("AzurLane Tachie Helper"))
        self.setWindowIcon(QPixmap("ico/cheshire.ico"))
        self.resize(300, 50)

        self.data = data
        self.names = sorted([k.removeprefix("painting/") for k in data.keys() if not k.endswith("_tex")])

        self.label = QLabel("painting/")

        self.completer = QCompleter(self.names)
        self.completer.setMaxVisibleItems(20)

        self.combo_box = QComboBox()
        self.combo_box.addItems(self.names)
        self.combo_box.setEditable(True)
        self.combo_box.setEditText("")
        self.combo_box.setMaxVisibleItems(20)
        self.combo_box.setCompleter(self.completer)

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
        deps = self.data[f"painting/{name}"]
        name_stem = name.removesuffix("_n")
        if (face := f"paintingface/{name_stem}") not in deps:
            deps += [face]
        icons = [f"{icon}/{name_stem}" for icon in ["shipyardicon", "squareicon", "herohrzicon"]]
        if len(AdbHelper.devices()) == []:
            AdbHelper.connect()
        AdbHelper.pull(f"painting/{name}", *deps, *icons, target=name)
        if os.path.exists(meta := f"{name}/painting/{name}"):
            os.rename(meta, f"{name}/{name}")
        self.accept()