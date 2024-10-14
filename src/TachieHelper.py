import os
from functools import partial

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

from .base import Config
from .base.Layer import prefered_layer
from .logger import logger
from .module import AssetManager
from .ui import IconViewer, Menu, Previewer, Table


class AzurLaneTachieHelper(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.tr("AzurLane Tachie Helper"))
        self.setAcceptDrops(True)
        self.resize(720, 560)

        Config.init()
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
        self.mOption = Menu.Option(self.onToggleAdvMode)

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
        Config.set("system", "RecentPath", file)
        name = os.path.basename(file)
        self.message.setText(f"({name}) {QDir.toNativeSeparators(file)}")
        logger.hr(name, 1)
        logger.attr("Metadata", f"'{file}'")

        self.tPainting.table.clearContents()
        self.tFace.table.clearContents()

        self.asset_manager.analyze(file)

        self.tPainting.set_data(self.asset_manager.deps, self.asset_manager.layers)

        face_layer = self.asset_manager.face_layer
        prefered = partial(prefered_layer, self.asset_manager.layers, face_layer)
        self.tFace.set_data(self.asset_manager.faces, face_layer, prefered)
        self.tIcon.set_data(self.asset_manager.icons, face_layer, prefered)

        self.preview.setAcceptDrops(True)
        self.mFile.aImportPainting.setEnabled(True)
        self.mFile.aImportFaces.setEnabled(True)
        self.mFile.aImportIcons.setEnabled(True)
        self.mEdit.aDecodeTexture.setEnabled(True)
        self.mEdit.aEncodeTexture.setEnabled(False)
        self.mEdit.aClipIcons.setEnabled(True)

    def onOpenMetadata(self):
        last = Config.get("system", "RecentPath")
        file, _ = QFileDialog.getOpenFileName(self, self.tr("Select Metadata"), last)
        if file:
            self.open_metadata(file)

    def onImportPainting(self):
        last = os.path.dirname(Config.get("system", "RecentPath"))
        files, _ = QFileDialog.getOpenFileNames(self, self.tr("Select Paintings"), last, "Image (*.png)")
        if files:
            flag = False
            for file in files:
                if self.tPainting.load(file):
                    flag = True
            if flag:
                self.preview.refresh()
                self.mEdit.aEncodeTexture.setEnabled(True)

    def onImportFaces(self):
        last = os.path.dirname(Config.get("system", "RecentPath"))
        dir = QFileDialog.getExistingDirectory(self, self.tr("Select Paintingface Folder"), last)
        if dir:
            if self.tFace.load(dir):
                self.preview.refresh()
                self.mEdit.aEncodeTexture.setEnabled(True)

    def import_icon(self, files: list[str]):
        flag = False
        for file in files:
            if self.tIcon.load(file):
                flag = True
        if flag:
            self.preview.refresh()
            self.mEdit.aEncodeTexture.setEnabled(True)

    def onImportIcons(self):
        last = os.path.dirname(Config.get("system", "RecentPath"))
        files, _ = QFileDialog.getOpenFileNames(self, self.tr("Select Icons"), last, "Image (*.png)")
        if files:
            self.import_icon(files)

    def onEditClip(self):
        last = os.path.dirname(Config.get("system", "RecentPath"))
        file, _ = QFileDialog.getOpenFileName(self, self.tr("Select Reference"), last, "Image (*.png)")
        if file:
            full, center = self.asset_manager.prepare_icon(file)
            viewer = IconViewer(self.asset_manager.meta.name_stem, self.asset_manager.icons, full, center)
            if viewer.exec():
                Config.set_presets(self.asset_manager.meta.name_stem, viewer.presets)
                res = self.asset_manager.clip_icons(file, viewer.presets)
                res = [QDir.toNativeSeparators(_) for _ in res]
                self.show_path("\n".join(res))
                self.import_icon(res)

    def onEditDecode(self):
        base = os.path.dirname(self.asset_manager.meta.path)
        res = self.asset_manager.decode(base)
        self.show_path(QDir.toNativeSeparators(res))

    def onEditEncode(self):
        base = os.path.dirname(self.asset_manager.meta.path)
        res = self.asset_manager.encode(base)
        self.show_path("\n".join([QDir.toNativeSeparators(_) for _ in res]))

    def onToggleAdvMode(self, value: bool):
        if self.tFace.table.rowCount() > 0:
            for i in range(self.tFace.num):
                if value:
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
            links = [x.toLocalFile() for x in event.mimeData().urls()]
            files = [x for x in links if os.path.isfile(x)]
            metadatas = [x for x in files if "." not in os.path.basename(x)]
            if metadatas != []:
                self.open_metadata(metadatas[0])
                event.accept()
            else:
                self.preview.dropEvent(event)
