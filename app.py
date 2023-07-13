import locale
import os
import sys

from PySide6.QtCore import QDir, QSettings, QTranslator
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
from src.utility import raw_name


class AzurLaneTachieHelper(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.tr("AzurLane Tachie Helper"))
        self.setWindowIcon(QPixmap("ico/cheshire.ico"))
        self.resize(720, 560)

        self.settings = QSettings("config.ini", QSettings.Format.IniFormat)

        self._init_ui()
        self._init_statusbar()
        self._init_menu()

        self.asset_manager = AssetManager()
        self.decoder = DecodeHelper(self.asset_manager)
        self.encoder = EncodeHelper(self.asset_manager)

    def _layout_abd(self):  # Layout for Assetbundle Dependencies
        label = QLabel(self.tr("Assetbundle Dependencies"))
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.tDependency = QTableWidget()
        self.tDependency.setColumnCount(2)
        self.tDependency.setHorizontalHeaderLabels([self.tr("Part Name"), self.tr("Full Path")])
        self.tDependency.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.tDependency.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tDependency.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding
        )

        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(self.tDependency)

        return layout

    def _layout_ir(self):  # Layout for Image Replacers
        label = QLabel(self.tr("Image Replacers"))
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.tReplacer = QTableWidget()
        self.tReplacer.setColumnCount(2)
        self.tReplacer.setHorizontalHeaderLabels([self.tr("Target"), self.tr("Image Source")])
        self.tReplacer.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.tReplacer.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tReplacer.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding
        )

        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(self.tReplacer)

        return layout

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.addLayout(self._layout_abd())
        layout.addLayout(self._layout_ir())

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

        self.mEdit = self.menuBar().addMenu(self.tr("Edit"))

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

    def onClickFileOpenMetadata(self):
        last = self.settings.value("File/Path", "")
        file, _ = QFileDialog.getOpenFileName(self, self.tr("Select Metadata to Open"), last)
        if file:
            self.settings.setValue("File/Path", file)
            self.message.setText(f"({os.path.basename(file)})  {QDir.toNativeSeparators(file) }")
            print("[INFO] Metadata:", file)

            self.tDependency.clearContents()
            self.tReplacer.clearContents()

            self.asset_manager.analyze(file)

            self.num_deps = len(self.asset_manager.deps)
            self.tDependency.setRowCount(self.num_deps)
            self.tReplacer.setRowCount(self.num_deps)
            for i, (k, v) in enumerate(self.asset_manager.deps.items()):
                x = self.tr("Not Found") if v is None else QDir.toNativeSeparators(v)
                self.tDependency.setItem(i, 0, QTableWidgetItem(k))
                self.tDependency.setItem(i, 1, QTableWidgetItem(x))
                self.tReplacer.setItem(i, 0, QTableWidgetItem(k))

            self.mFileImportPainting.setEnabled(True)
            self.mFileImportPaintingface.setEnabled(True)
            self.mEditDecode.setEnabled(True)

    def onClickFileImportPainting(self):
        last = os.path.dirname(self.settings.value("File/Path", ""))
        files, _ = QFileDialog.getOpenFileNames(
            self, self.tr("Select Paintings"), last, "Image (*.png)"
        )
        if files:
            print("[INFO] Paintings:")

            workload = {}
            for i in range(self.num_deps - 1):
                name = raw_name(self.tReplacer.item(i, 0).text()).lower()
                for file in files:
                    if os.path.splitext(os.path.basename(file))[0] == name:
                        path = QDir.toNativeSeparators(file)
                        self.tReplacer.setItem(i, 1, QTableWidgetItem(path))
                        workload |= {name: path}
                        break
            self.asset_manager.load_paintings(workload)

            self.mEditEncode.setEnabled(True)

    def onClickFileImportPaintingface(self):
        last = os.path.dirname(self.settings.value("File/Path", ""))
        dir = QFileDialog.getExistingDirectory(self, self.tr("Select Paintingface Folder"), last)
        if dir:
            print("[INFO] Paintingface folder:")
            print("      ", dir)
            print("[INFO] Paintingfaces:")

            path = QDir.toNativeSeparators(dir)
            self.tReplacer.setItem(self.num_deps - 1, 1, QTableWidgetItem(path))
            self.asset_manager.load_faces(path)

            self.mEditEncode.setEnabled(True)

    def onClickEditDecode(self):
        last = os.path.dirname(self.settings.value("File/Path", ""))
        dir = QFileDialog.getExistingDirectory(self, self.tr("Select Output Folder"), last)
        if dir:
            path = QDir.toNativeSeparators(self.decoder.exec(dir))
            msg_box = QMessageBox()
            msg_box.setText(self.tr("Successfully written into:") + f"\n{path}")
            msg_box.setStandardButtons(
                QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Ok
            )
            if msg_box.exec() == QMessageBox.StandardButton.Open:
                os.startfile(dir)

    def onClickEditEncode(self):
        last = os.path.dirname(self.settings.value("File/Path", ""))
        dir = QFileDialog.getExistingDirectory(self, dir=last)
        if dir:
            path = "\n".join([QDir.toNativeSeparators(_) for _ in self.encoder.exec(dir)])
            msg_box = QMessageBox()
            msg_box.setText(self.tr("Successfully written into:") + f"\n{path}")
            msg_box.setStandardButtons(
                QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Ok
            )
            if msg_box.exec() == QMessageBox.StandardButton.Open:
                os.startfile(dir)


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
