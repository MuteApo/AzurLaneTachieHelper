import os
import re

from PIL import Image
from PySide6.QtCore import QDir, Qt
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .AssetManager import AssetManager
from .Config import Config
from .ui import IconViewer, Menu, Previewer, Table


class AzurLaneTachieHelper(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.tr("AzurLane Tachie Helper"))
        self.setAcceptDrops(True)
        self.resize(720, 560)

        self.config = Config("config.ini")
        self.asset_manager = AssetManager()
        # self.encoder = EncodeHelper(self.asset_manager)

        self._init_ui()
        self._init_statusbar()
        self._init_menu()

    def _layout_face_repl(self):  # Layout for Paintingface Replacers
        label = QLabel(self.tr("Paintingface Replacers"))
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.tFaceRepl = QTableWidget()
        self.tFaceRepl.setColumnCount(2)
        self.tFaceRepl.setHorizontalHeaderLabels([self.tr("Clip"), self.tr("Image Source")])
        self.tFaceRepl.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.tFaceRepl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tFaceRepl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(self.tFaceRepl)

        return layout

    def _init_ui(self):
        self.preview = Previewer()

        self.tDep = Table.Dep(self.preview)

        left = QVBoxLayout()
        left.addLayout(self.tDep)
        # left.addLayout(self._layout_paint_repl())
        left.addLayout(self._layout_face_repl())

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)

        layout = QHBoxLayout()
        layout.addLayout(left)
        layout.addWidget(sep)
        layout.addWidget(self.preview)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def _init_statusbar(self):
        self.message = QLabel(self.tr("Ready"))
        self.message.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.statusBar().addWidget(self.message)
        self.statusBar().setStyleSheet("QStatusBar::item{border:0px}")

    def _init_menu(self):
        callbacks = {
            "Open Metadata": self.onClickFileOpenMetadata,
            "Import Painting": self.onClickFileImportPainting,
            "Import Paintingface": self.onClickFileImportPaintingface,
            "Import Icons": self.onClickFileImportIcons,
            "Clip Icons": self.onClickEditClip,
            "Decode Texture": self.onClickEditDecode,
            "Encode Texture": self.onClickEditEncode,
            "Dump Intermediate Layers": self.onClickOption,
            "Advanced Paintingface Mode": self.onClickOption,
            "Replace Icons": self.onClickOption,
        }
        self.mFile = Menu.File(callbacks)
        self.mEdit = Menu.Edit(callbacks)
        self.mOption = Menu.Option(callbacks, self.config)

        self.menuBar().addMenu(self.mFile)
        self.menuBar().addMenu(self.mEdit)
        self.menuBar().addMenu(self.mOption)

    def show_path(self, text: str):
        msg_box = QMessageBox()
        msg_box.setText(self.tr("Successfully written into:") + f"\n{text}")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()

    def open_metadata(self, file: str):
        self.config.set("File/RecentPath", file)
        self.message.setText(f"({os.path.basename(file)})  {QDir.toNativeSeparators(file)}")
        print("[INFO] Metadata:", file)

        self.tDep.table.clearContents()
        self.tFaceRepl.clearContents()

        self.asset_manager.analyze(file)

        # self.num_deps = len(self.asset_manager.deps)
        self.num_faces = len(self.asset_manager.faces)
        # self.tDep.setRowCount(self.num_deps)
        self.tFaceRepl.setRowCount(self.num_faces)

        self.tDep.set_data(self.asset_manager.deps, self.asset_manager.layers)

        # self.check_box: dict[str, QTableWidgetItem] = {}
        # for i, x in enumerate(self.asset_manager.faces):
        #     item = QTableWidgetItem(self.tDep.get_text(self.tDep.num - 1) + f"/{x}")
        #     item.setCheckState(Qt.CheckState.Checked)
        #     item.setFlags(~Qt.ItemFlag.ItemIsEnabled)
        #     self.tFaceRepl.setItem(i, 0, item)
        #     self.check_box[x] = item

        self.mFile.aImportPainting.setEnabled(True)
        self.mFile.aImportPaintingface.setEnabled(True)
        self.mFile.aImportIcons.setEnabled(True)
        self.mEdit.aDecodeTexture.setEnabled(True)
        self.mEdit.aClipIcons.setEnabled(True)

    def onClickFileOpenMetadata(self):
        last = self.config.get_str("File/RecentPath")
        file, _ = QFileDialog.getOpenFileName(self, self.tr("Select Metadata"), last)
        if file:
            self.open_metadata(file)

    def onClickFileImportPainting(self):
        last = os.path.dirname(self.config.get_str("File/RecentPath"))
        files, _ = QFileDialog.getOpenFileNames(
            self, self.tr("Select Paintings"), last, "Image (*.png)"
        )
        if files:
            print("[INFO] Paintings:")

            workload = {}
            for i in range(self.num_deps - 1):
                name = self.asset_manager.maps[self.tPaintRepl.item(i, 0).text()]
                for file in files:
                    if os.path.splitext(os.path.basename(file))[0] == name:
                        path = QDir.toNativeSeparators(file)
                        self.tPaintRepl.setItem(i, 1, QTableWidgetItem(path))
                        workload |= {name: path}
                        break
            self.asset_manager.load_paintings(workload)

            self.mEdit.aEncodeTexture.setEnabled(True)

    def onClickFileImportPaintingface(self):
        last = os.path.dirname(self.config.get_str("File/RecentPath"))
        dir = QFileDialog.getExistingDirectory(self, self.tr("Select Paintingface Folder"), last)
        if dir:
            print("[INFO] Paintingface folder:")
            print("      ", QDir.toNativeSeparators(dir))
            print("[INFO] Paintingfaces:")

            pics = {}
            for file in os.listdir(dir):
                name, _ = os.path.splitext(file)
                if re.match(r"^0|([1-9][0-9]*)$", name):
                    pics[name] = file
            workload = {}
            for i in range(self.num_faces):
                id = os.path.basename(self.tFaceRepl.item(i, 0).text())
                path = QDir.toNativeSeparators(os.path.join(dir, pics[id]))
                self.tFaceRepl.setItem(i, 1, QTableWidgetItem(path))
                if self.adv_mode:
                    item = self.tFaceRepl.item(i, 0)
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(Qt.CheckState.Checked)
                workload |= {id: path}
            self.asset_manager.load_faces(workload)

            self.mEdit.aEncodeTexture.setEnabled(True)

    def onClickFileImportIcons(self):
        last = os.path.dirname(self.config.get_str("File/RecentPath"))
        files, _ = QFileDialog.getOpenFileNames(
            self, self.tr("Select Icons"), last, "Image (*.png)"
        )
        if files:
            print("[INFO] Icons:")

            for file in files:
                name, _ = os.path.splitext(os.path.basename(file))
                if name in ["shipyardicon", "squareicon", "herohrzicon"]:
                    print("      ", QDir.toNativeSeparators(file))
                    self.asset_manager.repls[name] = Image.open(file)

            self.mEdit.aEncodeTexture.setEnabled(True)

    def onClickEditClip(self):
        last = os.path.dirname(self.config.get_str("File/RecentPath"))
        file, _ = QFileDialog.getOpenFileName(
            self, self.tr("Select Reference"), last, "Image (*.png)"
        )
        if file:
            viewer = IconViewer(self.asset_manager.icons, *self.asset_manager.prepare_icon(file))
            if viewer.exec():
                res = self.asset_manager.clip_icons(file, viewer.presets)
                self.show_path("\n".join([QDir.toNativeSeparators(_) for _ in res]))

    def onClickEditDecode(self):
        last = os.path.dirname(self.config.get_str("File/RecentPath", ""))
        dir = QFileDialog.getExistingDirectory(self, self.tr("Select Output Folder"), last)
        if dir:
            res = self.asset_manager.decode(dir, self.config.get_bool("Edit/DumpLayer"))
            self.show_path(QDir.toNativeSeparators(res))

    def onClickEditEncode(self):
        last = os.path.dirname(self.config.get_str("File/RecentPath"))
        dir = QFileDialog.getExistingDirectory(self, dir=last)
        if dir:
            is_clip = {
                k: v.checkState() != Qt.CheckState.Unchecked for k, v in self.check_box.items()
            }
            res = self.encoder.exec(dir, self.replace_icon, self.adv_mode, is_clip)
            self.show_path("\n".join([QDir.toNativeSeparators(_) for _ in res]))

    def onClickOption(self):
        self.config.set("Edit/DumpLayer", self.mOption.aDumpLayer.isChecked())

        adv_mode = self.mOption.aAdvMode.isChecked()
        if adv_mode != self.config.get_bool("Edit/AdvancedMode"):
            self.config.set("Edit/AdvancedMode", adv_mode)
            if hasattr(self, "num_faces"):
                for i in range(self.num_faces):
                    if adv_mode:
                        flag = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
                    else:
                        flag = ~Qt.ItemFlag.ItemIsEnabled
                    self.tFaceRepl.item(i, 0).setFlags(flag)

        self.config.set("Edit/ReplaceIcon", self.mOption.aReplaceIcons.isChecked())

    def dragEnterEvent(self, event: QDragEnterEvent):
        # print("dragEnter")
        if event.mimeData().hasUrls:
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        # print("dragMove")
        if event.mimeData().hasUrls:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        # print("drop")
        if event.mimeData().hasUrls:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            links = []
            for url in event.mimeData().urls():
                links.append(str(url.toLocalFile()))
            self.open_metadata(links[0])
        else:
            event.ignore()
