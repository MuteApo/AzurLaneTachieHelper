import os
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QDir, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from .base import Config
from .base.Data import FaceModeType
from .base.Layer import prefered_layer
from .logger import logger
from .module.AssetManager import AssetManager
from .ui import Menu
from .ui.IconViewer import IconViewer
from .ui.Previewer import Previewer
from .ui.Table import IconTable, PaintingfaceTable, PaintingTable


class AzurLaneTachieHelper(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.tr("AzurLane Tachie Helper"))
        self.setAcceptDrops(True)
        self.resize(960, 540)

        Config.init()
        self.asset_manager = AssetManager()

        self.face_mode_map = {
            FaceModeType.Off: self.tr("Off"),
            FaceModeType.Auto: self.tr("Auto"),
            FaceModeType.Custom: self.tr("Custom"),
        }
        self.server_map = {"CN": self.tr("CN"), "JP": self.tr("JP"), "EN": self.tr("EN")}

        self._init_statusbar()
        self._init_menu()
        self._init_ui()

    def _init_statusbar(self):
        self.msg_file = QLabel(self.tr("Ready"))
        self.msg_face_mode = QLabel()
        self.msg_server = QLabel()

        self.statusBar().addWidget(self.msg_file)
        self.statusBar().addPermanentWidget(self.msg_face_mode)
        self.statusBar().addPermanentWidget(self.msg_server)

    def _init_ui(self):
        self.preview = Previewer(self.mEdit.aEncodeTexture)
        self.tPainting = PaintingTable(self.preview)
        self.tFace = PaintingfaceTable(self.preview)
        self.tIcon = IconTable(self.preview)
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
        self.mOption = Menu.Option(self.refresh_statusbar, self.onToggleFaceMode)

        self.menuBar().addMenu(self.mFile)
        self.menuBar().addMenu(self.mEdit)
        self.menuBar().addMenu(self.mOption)

    def refresh_statusbar(self):
        face_mode = self.face_mode_map[Config.get_face_mode()]
        self.msg_face_mode.setText(self.tr("Paintingface Mode") + self.tr(": ") + face_mode)

        server = self.server_map[Config.get_server()]
        self.msg_server.setText(self.tr("Server") + self.tr(": ") + server)

    def show_path(self, text: str):
        msg_box = QMessageBox()
        msg_box.setWindowTitle(self.tr("AzurLane Tachie Helper"))
        msg_box.setText(self.tr("Successfully written into") + self.tr(": ") + f"\n{text}")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()

    def open_metadata(self, file: str):
        Config.set_recent_path(file)
        name = os.path.basename(file)
        self.msg_file.setText(f"({name}) {QDir.toNativeSeparators(file)}")
        logger.hr(name, 1)
        logger.attr("Metadata", file)

        self.tPainting.table.clearContents()
        self.tFace.table.clearContents()
        self.tIcon.table.clearContents()

        self.asset_manager.analyze(file)

        self.tPainting.set_data(self.asset_manager.layers)

        face_layer = self.asset_manager.face_layer
        prefered = prefered_layer(self.asset_manager.layers, face_layer)
        self.tFace.set_data(self.asset_manager.faces, face_layer, prefered)
        self.tIcon.set_data(self.asset_manager.icons, face_layer)

        self.preview.setAcceptDrops(True)
        self.mFile.aImportPainting.setEnabled(True)
        self.mFile.aImportFaces.setEnabled(True)
        self.mFile.aImportIcons.setEnabled(True)
        self.mEdit.aDecodeTexture.setEnabled(True)
        self.mEdit.aEncodeTexture.setEnabled(False)
        self.mEdit.aClipIcons.setEnabled(True)

    def onOpenMetadata(self):
        last = Config.get_recent_path()
        file, _ = QFileDialog.getOpenFileName(self, self.tr("Select Metadata"), last)
        if file:
            self.open_metadata(file)

    def onImportPainting(self):
        last = os.path.dirname(Config.get_recent_path())
        files, _ = QFileDialog.getOpenFileNames(self, self.tr("Select Paintings"), last, "Image (*.png)")
        if files:
            with ThreadPoolExecutor(max_workers=8) as executor:
                executor.map(self.tPainting.load, files)
            self.preview.refresh()
            self.mEdit.aEncodeTexture.setEnabled(True)

    def onImportFaces(self):
        last = os.path.dirname(Config.get_recent_path())
        dir = QFileDialog.getExistingDirectory(self, self.tr("Select Paintingface Folder"), last)
        if dir:
            self.tFace.load(dir)
            self.preview.refresh()
            self.mEdit.aEncodeTexture.setEnabled(True)

    def import_icon(self, files: list[str]):
        with ThreadPoolExecutor(max_workers=8) as executor:
            executor.map(self.tIcon.load, files)
        self.preview.refresh()
        self.mEdit.aEncodeTexture.setEnabled(True)

    def onImportIcons(self):
        last = os.path.dirname(Config.get_recent_path())
        files, _ = QFileDialog.getOpenFileNames(self, self.tr("Select Icons"), last, "Image (*.png)")
        if files:
            self.import_icon(files)

    def onEditClip(self):
        last = os.path.dirname(Config.get_recent_path())
        file, _ = QFileDialog.getOpenFileName(self, self.tr("Select Reference"), last, "Image (*.png)")
        if file:
            full, center = self.asset_manager.prepare_icon(file)
            viewer = IconViewer(self.asset_manager.meta.name_stem, self.asset_manager.icons, full, center)
            if viewer.exec():
                Config.set_presets(self.asset_manager.meta.name_stem, viewer.presets)
                res = self.asset_manager.clip_icons(file, viewer.presets)
                self.import_icon(res)

    def onEditDecode(self):
        base = os.path.dirname(self.asset_manager.meta.path)
        res = self.asset_manager.decode(base)
        self.show_path(QDir.toNativeSeparators(res))

    def onEditEncode(self):
        base = os.path.dirname(self.asset_manager.meta.path)
        res = self.asset_manager.encode(base)
        self.show_path("\n".join(map(QDir.toNativeSeparators, res)))

    def onToggleFaceMode(self):
        if hasattr(self.tPainting, "layers"):
            with ThreadPoolExecutor(max_workers=8) as executor:
                executor.map(lambda x: x.refresh(), self.tPainting.layers.values())
            self.preview.refresh()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            if not event.isAccepted():
                event.accept()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.DropAction.CopyAction)
            files = filter(os.path.isfile, map(lambda x: x.toLocalFile(), event.mimeData().urls()))
            metadatas = list(filter(lambda x: "." not in os.path.basename(x), files))
            if metadatas != []:
                self.open_metadata(metadatas[0])
                event.accept()
            else:
                self.preview.dropEvent(event)
