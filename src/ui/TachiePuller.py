import os
from zipfile import ZipFile

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
)

from ..base import Config
from ..logger import logger
from ..module.AdbHelper import AdbHelper


class TachiePuller(QDialog):
    def __init__(self, data: dict[str, list[str]]):
        super().__init__()
        self.setWindowTitle(self.tr("AzurLane Tachie Helper"))
        self.setWindowIcon(QPixmap("ico/cheshire.ico"))
        self.resize(300, 50)

        self.data = data
        self.metas = sorted([k.removeprefix("painting/") for k in data.keys() if not k.endswith("_tex")])
        self.names = list(filter(lambda x: not x.endswith("_n") and not x.endswith("_hx"), self.metas))

        self.label = QLabel(Config.get_package() + ":")

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
        if AdbHelper.devices() == []:
            AdbHelper.connect()
        name = self.combo_box.currentText()
        logger.attr("Metadata", name)

        deps = [f"painting/{name}"] + self.data.get(f"painting/{name}", [])
        if f"{name}_n" in self.metas:
            deps.extend([f"painting/{name}_n"] + self.data.get(f"painting/{name}_n", []))
        if f"paintingface/{name}" not in deps:
            deps += [f"paintingface/{name}"]

        deps = sorted(set(deps), key=lambda x: tuple(map(len, x.split("/"))))
        icons = [f"{icon}/{name}" for icon in ["shipyardicon", "herohrzicon", "squareicon"]]

        _, failed = AdbHelper.pull(*deps, *icons, dst_dir=f"projects/{name}", add_prefix=True)
        if failed != []:
            if not os.path.exists("base.apk"):
                apk = AdbHelper.exec_out("ls", "-R", f"/data/app/*/{Config.get_package()}*/*.apk", as_root=True)
                AdbHelper.pull(apk, progress=True, log=False)

            with ZipFile("base.apk") as z:
                for file in [f"{x}.ys" if "icon" in x else x for x in failed]:
                    try:
                        with z.open(f"assets/AssetBundles/{file}") as i, open(f"projects/{name}/{file}", "wb") as o:
                            o.write(i.read())
                    except:
                        logger.warning(f"[bold][[red]Failed[/red]][/bold] {file}")
                    else:
                        logger.info(f"[bold][[green]Succeeded[/green]][/bold] {file}")

        if os.path.exists(meta := f"projects/{name}/painting/{name}"):
            os.replace(meta, f"projects/{name}/{name}")
        if os.path.exists(meta := f"projects/{name}/painting/{name}_n"):
            os.replace(meta, f"projects/{name}/{name}_n")

        self.accept()
