import locale
import os
import re
import sys

from PIL import Image
from PySide6.QtCore import QDir, QSettings, Qt, QTranslator
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QSpacerItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.AssetManager import AssetManager
from src.DecodeHelper import DecodeHelper
from src.EncodeHelper import EncodeHelper


class AzurLaneTachieHelper(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.tr("AzurLane Tachie Helper"))
        self.setWindowIcon(QPixmap("ico/cheshire.ico"))
        self.resize(720, 560)

        self.settings = QSettings("config.ini", QSettings.Format.IniFormat)
        self._read_ini()

        self._init_ui()
        self._init_statusbar()
        self._init_menu()

        self.asset_manager = AssetManager()
        self.decoder = DecodeHelper(self.asset_manager)
        self.encoder = EncodeHelper(self.asset_manager)

    def _get_conf_bool(self, key: str, default: bool) -> bool:
        value = {True: "true", False: "false"}[default]
        return eval(str(self.settings.value(key, value)).capitalize())

    def _read_ini(self):
        # self.remove_old = self._get_conf_bool("Edit/RemoveOld", True)
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

    def _init_menu(self):
        self.mFile = self.menuBar().addMenu(self.tr("File"))

        self.mFileOpenMetadata = self.mFile.addAction(self.tr("Open Metadata"))
        self.mFileOpenMetadata.triggered.connect(self.onClickFileOpenMetadata)
        self.mFileOpenMetadata.setCheckable(False)
        self.mFileOpenMetadata.setEnabled(True)
        self.mFileOpenMetadata.setShortcut("Ctrl+M")

        self.mFileImportPainting = self.mFile.addAction(self.tr("Import Painting"))
        self.mFileImportPainting.triggered.connect(self.onClickFileImportPainting)
        self.mFileImportPainting.setCheckable(False)
        self.mFileImportPainting.setEnabled(False)
        self.mFileImportPainting.setShortcut("Ctrl+P")

        self.mFileImportPaintingface = self.mFile.addAction(self.tr("Import Paintingface"))
        self.mFileImportPaintingface.triggered.connect(self.onClickFileImportPaintingface)
        self.mFileImportPaintingface.setCheckable(False)
        self.mFileImportPaintingface.setEnabled(False)
        self.mFileImportPaintingface.setShortcut("Ctrl+F")

        self.mFileImportIcons = self.mFile.addAction(self.tr("Import Icons"))
        self.mFileImportIcons.triggered.connect(self.onClickFileImportIcons)
        self.mFileImportIcons.setCheckable(False)
        self.mFileImportIcons.setEnabled(False)
        self.mFileImportIcons.setShortcut("Ctrl+I")

        self.mEdit = self.menuBar().addMenu(self.tr("Edit"))

        self.mEditClip = self.mEdit.addAction(self.tr("Clip Icons"))
        self.mEditClip.triggered.connect(self.onClickEditClip)
        self.mEditClip.setCheckable(False)
        self.mEditClip.setEnabled(False)
        self.mEditClip.setShortcut("Ctrl+C")

        self.mEditDecode = self.mEdit.addAction(self.tr("Decode Texture"))
        self.mEditDecode.triggered.connect(self.onClickEditDecode)
        self.mEditDecode.setCheckable(False)
        self.mEditDecode.setEnabled(False)
        self.mEditDecode.setShortcut("Ctrl+D")

        self.mEditEncode = self.mEdit.addAction(self.tr("Encode Texture"))
        self.mEditEncode.triggered.connect(self.onClickEditEncode)
        self.mEditEncode.setCheckable(False)
        self.mEditEncode.setEnabled(False)
        self.mEditEncode.setShortcut("Ctrl+E")

        self.mOption = self.menuBar().addMenu(self.tr("Option"))

        self.mOptionDumpLayer = self.mOption.addAction(self.tr("Dump Intermediate Layers"))
        self.mOptionDumpLayer.triggered.connect(self.onClickOption)
        self.mOptionDumpLayer.setCheckable(True)
        self.mOptionDumpLayer.setChecked(self.dump_layer)

        self.mOptionAdvMode = self.mOption.addAction(self.tr("Advanced Paintingface Mode"))
        self.mOptionAdvMode.triggered.connect(self.onClickOption)
        self.mOptionAdvMode.setCheckable(True)
        self.mOptionAdvMode.setChecked(self.adv_mode)

        self.mOptionReplaceIcons = self.mOption.addAction(self.tr("Replace Icons"))
        self.mOptionReplaceIcons.triggered.connect(self.onClickOption)
        self.mOptionReplaceIcons.setCheckable(True)
        self.mOptionReplaceIcons.setChecked(self.replace_icon)

    def onClickFileOpenMetadata(self):
        last = self.settings.value("File/RecentPath", "")
        file, _ = QFileDialog.getOpenFileName(self, self.tr("Select Metadata"), last)
        if file:
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

            self.check_box: list[QTableWidgetItem] = []
            for i in range(self.num_faces):
                x = self.tDep.item(self.num_deps - 1, 0).text() + f"/{i+1}"
                item = QTableWidgetItem(x)
                item.setCheckState(Qt.CheckState.PartiallyChecked)
                item.setFlags(~Qt.ItemFlag.ItemIsEnabled)
                self.tFaceRepl.setItem(i, 0, item)
                self.check_box += [item]

            self.mFileImportPainting.setEnabled(True)
            self.mFileImportPaintingface.setEnabled(True)
            self.mFileImportIcons.setEnabled(True)
            self.mEditDecode.setEnabled(True)
            self.mEditClip.setEnabled(True)

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

            self.mEditEncode.setEnabled(True)

    def onClickFileImportPaintingface(self):
        last = os.path.dirname(self.settings.value("File/RecentPath", ""))
        dir = QFileDialog.getExistingDirectory(self, self.tr("Select Paintingface Folder"), last)
        if dir:
            print("[INFO] Paintingface folder:")
            print("      ", QDir.toNativeSeparators(dir))
            print("[INFO] Paintingfaces:")

            workload = {}
            for file in os.listdir(dir):
                name, _ = os.path.splitext(file)
                if re.match(r"^0|([1-9][0-9]*)$", name):
                    id = int(name)
                    path = QDir.toNativeSeparators(os.path.join(dir, file))
                    self.tFaceRepl.setItem(id - 1, 1, QTableWidgetItem(path))
                    if self.adv_mode:
                        self.tFaceRepl.item(id - 1, 0).setFlags(
                            Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
                        )
                        self.tFaceRepl.item(id - 1, 0).setCheckState(Qt.CheckState.Checked)
                    workload |= {id: path}
            self.asset_manager.load_faces(workload)

            self.mEditEncode.setEnabled(True)

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
                    self.asset_manager.icons[name] = Image.open(file)

            self.mEditEncode.setEnabled(True)

    def onClickEditClip(self):
        last = os.path.dirname(self.settings.value("File/RecentPath", ""))
        file, _ = QFileDialog.getOpenFileName(
            self, self.tr("Select Reference"), last, "Image (*.png)"
        )
        if file:
            res = self.asset_manager.clip_icons(file)
            path = "\n".join([QDir.toNativeSeparators(_) for _ in res])
            msg_box = QMessageBox()
            msg_box.setText(self.tr("Successfully written into:") + f"\n{path}")
            msg_box.layout().addItem(
                QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            )
            msg_box.setStandardButtons(
                QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Ok
            )
            if msg_box.exec() == QMessageBox.StandardButton.Open:
                os.startfile(dir)

    def onClickEditDecode(self):
        last = os.path.dirname(self.settings.value("File/RecentPath", ""))
        dir = QFileDialog.getExistingDirectory(self, self.tr("Select Output Folder"), last)
        if dir:
            path = QDir.toNativeSeparators(self.decoder.exec(dir, self.dump_layer))
            msg_box = QMessageBox()
            msg_box.setText(self.tr("Successfully written into:") + f"\n{path}")
            msg_box.setStandardButtons(
                QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Ok
            )
            if msg_box.exec() == QMessageBox.StandardButton.Open:
                os.startfile(dir)

    def onClickEditEncode(self):
        last = os.path.dirname(self.settings.value("File/RecentPath", ""))
        dir = QFileDialog.getExistingDirectory(self, dir=last)
        if dir:
            is_clip = [_.checkState() != Qt.CheckState.Unchecked for _ in self.check_box]
            res = self.encoder.exec(dir, self.replace_icon, self.adv_mode, is_clip)
            path = "\n".join([QDir.toNativeSeparators(_) for _ in res])
            msg_box = QMessageBox()
            msg_box.setText(self.tr("Successfully written into:") + f"\n{path}")
            msg_box.layout().addItem(
                QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            )
            msg_box.setStandardButtons(
                QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Ok
            )
            if msg_box.exec() == QMessageBox.StandardButton.Open:
                os.startfile(dir)

    def onClickOption(self):
        self.dump_layer = self.mOptionDumpLayer.isChecked()
        self.settings.setValue("Edit/DumpLayer", self.dump_layer)

        adv_mode = self.mOptionAdvMode.isChecked()
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

        self.replace_icon = self.mOptionReplaceIcons.isChecked()
        self.settings.setValue("Edit/ReplaceIcon", self.replace_icon)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    path = os.path.join("i18n", locale.getdefaultlocale()[0] + ".qm")
    if os.path.exists(path):
        trans = QTranslator(app)
        trans.load(path)
        app.installTranslator(trans)

    win = AzurLaneTachieHelper()
    win.show()

    app.exec()
