import os
import re

from PIL import Image
from PySide6.QtCore import QDir, QSettings, Qt
from PySide6.QtGui import QAction, QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .AssetManager import AssetManager
from .IconViewer import IconViewer


class AzurLaneTachieHelper(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.tr("AzurLane Tachie Helper"))
        self.setAcceptDrops(True)
        self.resize(720, 560)

        self.settings = QSettings("config.ini", QSettings.Format.IniFormat)
        self._read_ini()

        self._init_ui()
        self._init_statusbar()
        self._init_action()
        self._init_menu()

        self.asset_manager = AssetManager()
        # self.decoder = DecodeHelper(self.asset_manager)
        # self.encoder = EncodeHelper(self.asset_manager)

    def _get_conf_bool(self, key: str, default: bool) -> bool:
        value = {True: "true", False: "false"}[default]
        return eval(str(self.settings.value(key, value)).capitalize())

    def _read_ini(self):
        self.dump_layer = self._get_conf_bool("Edit/DumpLayer", False)
        self.adv_mode = self._get_conf_bool("Edit/AdvancedMode", False)
        self.replace_icon = self._get_conf_bool("Edit/ReplaceIcon", False)

    def _layout_ab_dep(self):  # Layout for Assetbundle Dependencies
        label = QLabel(self.tr("Assetbundle Dependencies"))
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.tDep = QTableWidget()
        self.tDep.setColumnCount(2)
        self.tDep.setHorizontalHeaderLabels([self.tr("Part Name"), self.tr("Full Path")])
        self.tDep.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.tDep.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tDep.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding
        )

        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(self.tDep)

        return layout

    def _layout_paint_repl(self):  # Layout for Painting Replacers
        label = QLabel(self.tr("Painting Replacers"))
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.tPaintRepl = QTableWidget()
        self.tPaintRepl.setColumnCount(2)
        self.tPaintRepl.setHorizontalHeaderLabels([self.tr("Target"), self.tr("Image Source")])
        self.tPaintRepl.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.tPaintRepl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tPaintRepl.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding
        )

        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(self.tPaintRepl)

        return layout

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
        self.tFaceRepl.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding
        )

        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(self.tFaceRepl)

        return layout

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.addLayout(self._layout_ab_dep())
        layout.addLayout(self._layout_paint_repl())
        layout.addLayout(self._layout_face_repl())

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def _init_statusbar(self):
        self.message = QLabel(self.tr("Ready"))
        self.message.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.statusBar().addWidget(self.message)
        self.statusBar().setStyleSheet("QStatusBar::item{border:0px}")

    def _init_action(self):
        self.aFileOpenMetadata = QAction(
            self.tr("Open Metadata"),
            self,
            shortcut="Ctrl+M",
            enabled=True,
            triggered=self.onClickFileOpenMetadata,
        )
        self.aFileImportPainting = QAction(
            self.tr("Import Painting"),
            self,
            shortcut="Ctrl+P",
            enabled=False,
            triggered=self.onClickFileImportPainting,
        )
        self.aFileImportPaintingface = QAction(
            self.tr("Import Paintingface"),
            self,
            shortcut="Ctrl+F",
            enabled=False,
            triggered=self.onClickFileImportPaintingface,
        )
        self.aFileImportIcons = QAction(
            self.tr("Import Icons"),
            self,
            shortcut="Ctrl+I",
            enabled=False,
            triggered=self.onClickFileImportIcons,
        )

        self.aEditClipIcons = QAction(
            self.tr("Clip Icons"),
            self,
            shortcut="Ctrl+C",
            enabled=False,
            triggered=self.onClickEditClip,
        )
        self.aEditDecodeTexture = QAction(
            self.tr("Decode Texture"),
            self,
            shortcut="Ctrl+D",
            enabled=False,
            triggered=self.onClickEditDecode,
        )
        self.aEditEncodeTexture = QAction(
            self.tr("Encode Texture"),
            self,
            shortcut="Ctrl+E",
            enabled=False,
            triggered=self.onClickEditEncode,
        )

        self.aOptionDumpLayer = QAction(
            self.tr("Dump Intermediate Layers"),
            self,
            checkable=True,
            checked=self.dump_layer,
            triggered=self.onClickOption,
        )
        self.aOptionAdvMode = QAction(
            self.tr("Advanced Paintingface Mode"),
            self,
            checkable=True,
            checked=self.adv_mode,
            triggered=self.onClickOption,
        )
        self.aOptionReplaceIcons = QAction(
            self.tr("Replace Icons"),
            self,
            checkable=True,
            checked=self.replace_icon,
            triggered=self.onClickOption,
        )

    def _init_menu(self):
        self.mFile = QMenu(self.tr("File"), self)
        self.mFile.addAction(self.aFileOpenMetadata)
        self.mFile.addAction(self.aFileImportPainting)
        self.mFile.addAction(self.aFileImportPaintingface)
        self.mFile.addAction(self.aFileImportIcons)

        self.mEdit = QMenu(self.tr("Edit"), self)
        self.mEdit.addAction(self.aEditClipIcons)
        self.mEdit.addAction(self.aEditDecodeTexture)
        self.mEdit.addAction(self.aEditEncodeTexture)

        self.mOption = QMenu(self.tr("Option"), self)
        self.mOption.addAction(self.aOptionDumpLayer)
        self.mOption.addAction(self.aOptionAdvMode)
        self.mOption.addAction(self.aOptionReplaceIcons)

        self.menuBar().addMenu(self.mFile)
        self.menuBar().addMenu(self.mEdit)
        self.menuBar().addMenu(self.mOption)

    def show_path(self, text: str):
        msg_box = QMessageBox()
        msg_box.setText(self.tr("Successfully written into:") + f"\n{text}")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()

    def open_metadata(self, file: str):
        self.settings.setValue("File/RecentPath", file)
        self.message.setText(f"({os.path.basename(file)})  {QDir.toNativeSeparators(file)}")
        print("[INFO] Metadata:", file)

        self.tDep.clearContents()
        self.tPaintRepl.clearContents()
        self.tFaceRepl.clearContents()

        self.asset_manager.analyze(file)

        self.num_deps = len(self.asset_manager.deps)
        self.num_faces = len(self.asset_manager.faces)
        self.tDep.setRowCount(self.num_deps)
        self.tPaintRepl.setRowCount(self.num_deps - 1)
        self.tFaceRepl.setRowCount(self.num_faces)
        for i, (k, v) in enumerate(self.asset_manager.deps.items()):
            x = self.tr("Not Found") if v is None else QDir.toNativeSeparators(v)
            self.tDep.setItem(i, 0, QTableWidgetItem(k))
            self.tDep.setItem(i, 1, QTableWidgetItem(x))

            self.tPaintRepl.setItem(i, 0, QTableWidgetItem(k))

        self.check_box: dict[str, QTableWidgetItem] = {}
        for i, x in enumerate(self.asset_manager.faces):
            item = QTableWidgetItem(self.tDep.item(self.num_deps - 1, 0).text() + f"/{x}")
            item.setCheckState(Qt.CheckState.Checked)
            item.setFlags(~Qt.ItemFlag.ItemIsEnabled)
            self.tFaceRepl.setItem(i, 0, item)
            self.check_box[x] = item

        self.aFileImportPainting.setEnabled(True)
        self.aFileImportPaintingface.setEnabled(True)
        self.aFileImportIcons.setEnabled(True)
        self.aEditDecodeTexture.setEnabled(True)
        self.aEditClipIcons.setEnabled(True)

    def onClickFileOpenMetadata(self):
        last = self.settings.value("File/RecentPath", "")
        file, _ = QFileDialog.getOpenFileName(self, self.tr("Select Metadata"), last)
        if file:
            self.open_metadata(file)

    def onClickFileImportPainting(self):
        last = os.path.dirname(self.settings.value("File/RecentPath", ""))
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

            self.aEditEncodeTexture.setEnabled(True)

    def onClickFileImportPaintingface(self):
        last = os.path.dirname(self.settings.value("File/RecentPath", ""))
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

            self.aEditEncodeTexture.setEnabled(True)

    def onClickFileImportIcons(self):
        last = os.path.dirname(self.settings.value("File/RecentPath", ""))
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

            self.aEditEncodeTexture.setEnabled(True)

    def onClickEditClip(self):
        last = os.path.dirname(self.settings.value("File/RecentPath", ""))
        file, _ = QFileDialog.getOpenFileName(
            self, self.tr("Select Reference"), last, "Image (*.png)"
        )
        if file:
            viewer = IconViewer(self.asset_manager.icons, *self.asset_manager.prepare_icon(file))
            if viewer.exec():
                res = self.asset_manager.clip_icons(file, viewer.presets)
                self.show_path("\n".join([QDir.toNativeSeparators(_) for _ in res]))

    def onClickEditDecode(self):
        last = os.path.dirname(self.settings.value("File/RecentPath", ""))
        dir = QFileDialog.getExistingDirectory(self, self.tr("Select Output Folder"), last)
        if dir:
            res = self.asset_manager.decode(dir, self.dump_layer)
            self.show_path(QDir.toNativeSeparators(res))

    def onClickEditEncode(self):
        last = os.path.dirname(self.settings.value("File/RecentPath", ""))
        dir = QFileDialog.getExistingDirectory(self, dir=last)
        if dir:
            is_clip = {
                k: v.checkState() != Qt.CheckState.Unchecked for k, v in self.check_box.items()
            }
            res = self.encoder.exec(dir, self.replace_icon, self.adv_mode, is_clip)
            self.show_path("\n".join([QDir.toNativeSeparators(_) for _ in res]))

    def onClickOption(self):
        self.dump_layer = self.aOptionDumpLayer.isChecked()
        self.settings.setValue("Edit/DumpLayer", self.dump_layer)

        adv_mode = self.aOptionAdvMode.isChecked()
        if adv_mode != self.adv_mode:
            self.adv_mode = adv_mode
            self.settings.setValue("Edit/AdvancedMode", adv_mode)
            if hasattr(self, "num_faces"):
                for i in range(self.num_faces):
                    if adv_mode:
                        flag = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
                    else:
                        flag = ~Qt.ItemFlag.ItemIsEnabled
                    self.tFaceRepl.item(i, 0).setFlags(flag)

        self.replace_icon = self.aOptionReplaceIcons.isChecked()
        self.settings.setValue("Edit/ReplaceIcon", self.replace_icon)

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
