import os

from PySide6.QtCore import QDir, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
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

        self._init_statusbar()
        self._init_menu()
        self._init_ui()

    def _init_statusbar(self):
        self.message = QLabel(self.tr("Ready"))
        self.message.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.statusBar().addWidget(self.message)
        self.statusBar().setStyleSheet("QStatusBar::item{border:0px}")

    def _init_ui(self):
        self.preview = Previewer(self.mEdit.aEncodeTexture)
        self.tPainting = Table.Painting(self.preview)
        self.tFace = Table.Paintingface(self.preview)
        self.tIcon = Table.Icon(self.preview)
        self.preview.set_callback(self.tPainting.load, self.tFace.load, self.tIcon.load)

        left = QVBoxLayout()
        left.addLayout(self.tPainting)
        left.addLayout(self.tFace)
        left.addLayout(self.tIcon)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)

        layout = QHBoxLayout()
        layout.addLayout(left)
        layout.addWidget(sep)
        layout.addWidget(self.preview)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def _init_menu(self):
        self.mFile = Menu.File(self.onOpenMetadata, self.onImportPainting, self.onImportFaces, self.onImportIcons)
        self.mEdit = Menu.Edit(self.onEditClip, self.onEditDecode, self.onEditEncode)
        self.mOption = Menu.Option(self.config, self.onOption, self.onOption)

        self.menuBar().addMenu(self.mFile)
        self.menuBar().addMenu(self.mEdit)
        self.menuBar().addMenu(self.mOption)

    def show_path(self, text: str):
        msg_box = QMessageBox()
        msg_box.setWindowTitle(self.tr("AzurLane Tachie Helper"))
        msg_box.setText(self.tr("Successfully written into:") + f"\n{text}")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()

    def open_metadata(self, file: str):
        self.config.set("system/RecentPath", file)
        self.message.setText(f"({os.path.basename(file)}) {QDir.toNativeSeparators(file)}")
        print("[INFO] Metadata:", file)

        self.tPainting.table.clearContents()
        self.tFace.table.clearContents()

        self.asset_manager.analyze(file)

        self.tPainting.set_data(self.asset_manager.deps, self.asset_manager.layers)

        face_layer = self.asset_manager.face_layer
        prefered = self.asset_manager.prefered(face_layer)
        adv_mode = self.config.get_bool("system/AdvancedMode")
        self.tFace.set_data(self.asset_manager.faces, face_layer, prefered, adv_mode)

        self.tIcon.set_data(self.asset_manager.icons, face_layer, prefered)

        self.mFile.aImportPainting.setEnabled(True)
        self.mFile.aImportPaintingface.setEnabled(True)
        self.mFile.aImportIcons.setEnabled(True)
        self.mEdit.aDecodeTexture.setEnabled(True)
        self.mEdit.aClipIcons.setEnabled(True)

    def onOpenMetadata(self):
        last = self.config.get_str("system/RecentPath")
        file, _ = QFileDialog.getOpenFileName(self, self.tr("Select Metadata"), last)
        if file:
            self.open_metadata(file)

    def onImportPainting(self):
        last = os.path.dirname(self.config.get_str("system/RecentPath"))
        files, _ = QFileDialog.getOpenFileNames(self, self.tr("Select Paintings"), last, "Image (*.png)")
        if files:
            flag = False
            for file in files:
                if self.tPainting.load(file):
                    flag = True
            if flag:
                self.mEdit.aEncodeTexture.setEnabled(True)

    def onImportFaces(self):
        last = os.path.dirname(self.config.get_str("system/RecentPath"))
        dir = QFileDialog.getExistingDirectory(self, self.tr("Select Paintingface Folder"), last)
        if dir:
            if self.tFace.load(dir):
                self.mEdit.aEncodeTexture.setEnabled(True)

    def import_icon(self, files: list[str]):
        flag = False
        for file in files:
            if self.tIcon.load(file):
                flag = True
        if flag:
            self.mEdit.aEncodeTexture.setEnabled(True)

    def onImportIcons(self):
        last = os.path.dirname(self.config.get_str("system/RecentPath"))
        files, _ = QFileDialog.getOpenFileNames(self, self.tr("Select Icons"), last, "Image (*.png)")
        if files:
            self.import_icon(files)

    def onEditClip(self):
        last = os.path.dirname(self.config.get_str("system/RecentPath"))
        file, _ = QFileDialog.getOpenFileName(self, self.tr("Select Reference"), last, "Image (*.png)")
        if file:
            presets = self.config.get_presets(self.asset_manager.meta.name_stem)
            full, center = self.asset_manager.prepare_icon(file)
            viewer = IconViewer(self.asset_manager.icons, presets, full, center)
            if viewer.exec():
                self.config.set_presets(self.asset_manager.meta.name_stem, viewer.presets)
                res = self.asset_manager.clip_icons(file, viewer.presets)
                res = [QDir.toNativeSeparators(_) for _ in res]
                self.show_path("\n".join(res))
                self.import_icon(res)

    def onEditDecode(self):
        base = os.path.dirname(self.asset_manager.meta.path)
        res = self.asset_manager.decode(base, self.config.get_bool("system/DumpLayer"))
        self.show_path(QDir.toNativeSeparators(res))

    def onEditEncode(self):
        base = os.path.dirname(self.asset_manager.meta.path)
        res = self.asset_manager.encode(base)
        self.show_path("\n".join([QDir.toNativeSeparators(_) for _ in res]))

    def onOption(self):
        self.config.set("system/DumpLayer", self.mOption.aDumpLayer.isChecked())

        adv_mode = self.mOption.aAdvMode.isChecked()
        if adv_mode != self.config.get_bool("system/AdvancedMode"):
            self.config.set("system/AdvancedMode", adv_mode)
            if hasattr(self, "num_faces"):
                for i in range(self.tFace.num):
                    if adv_mode:
                        flag = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
                    else:
                        flag = ~Qt.ItemFlag.ItemIsEnabled
                    self.tFace.table.item(i, 0).setFlags(flag)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            if not event.isAccepted():
                event.accept()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.DropAction.CopyAction)
            self.open_metadata(event.mimeData().urls()[0].toLocalFile())
            self.preview.setAcceptDrops(True)
            if event.isAccepted():
                self.mEdit.aEncodeTexture.setEnabled(True)
            else:
                event.accept()
