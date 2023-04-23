import os
import re
import sys
from pprint import pprint

from PySide6.QtCore import QSettings, Qt, Slot
from PySide6.QtGui import QAction, QFont, QFontMetrics, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qt_material import apply_stylesheet

from src.DecodeHelper import DecodeHelper
from src.EncodeHelper import EncodeHelper


class AzurLaneTachieHelper(QMainWindow):
    def __init__(self):
        super(AzurLaneTachieHelper, self).__init__()
        self.setWindowTitle("AzurLaneTachieHelper")
        self.setWindowIcon(QIcon("ico/cheshire.ico"))
        self.resize(720, 480)

        self.settings = QSettings("config.ini", QSettings.Format.IniFormat)

        self._init_ui()
        self._init_statusbar()
        self._init_menu()

        self.decoder = DecodeHelper()
        self.encoder = EncodeHelper()

    def _layout_abd(self):  # Layout for Assetbundle Dependencies
        label = QLabel("Assetbundle Dependencies")
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.tDependency = QTableWidget()
        self.tDependency.setColumnCount(2)
        self.tDependency.setHorizontalHeaderLabels(["Part Name", "Full Path"])
        self.tDependency.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.tDependency.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.tDependency.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed
        )

        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(self.tDependency)

        return layout

    def _layout_ir(self):  # Layout for Image Replacers
        label = QLabel("Image Replacers")
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.tReplacer = QTableWidget()
        self.tReplacer.setColumnCount(2)
        self.tReplacer.setHorizontalHeaderLabels(["Target", "Image Source"])
        self.tReplacer.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.tReplacer.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.tReplacer.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed
        )

        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(self.tReplacer)

        return layout

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.addLayout(self._layout_abd())
        layout.addLayout(self._layout_ir())
        layout.addItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        )

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def _init_statusbar(self):
        self.message = QLabel("Ready")
        self.message.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.statusBar().addWidget(self.message)
        self.statusBar().setStyleSheet("QStatusBar::item{border:0px}")

    def _init_menu(self):
        self.mFile = self.menuBar().addMenu("&File")

        self.mFileOpenMetadata = self.mFile.addAction("&Open Metadata")
        self.mFileOpenMetadata.triggered.connect(self.onClickFileOpenMetadata)
        self.mFileOpenMetadata.setCheckable(True)
        self.mFileOpenMetadata.setShortcut("Ctrl+M")

        self.mFileImportReplacers = self.mFile.addAction("&Import Replacers")
        self.mFileImportReplacers.triggered.connect(self.onClickFileImportReplacers)
        self.mFileImportReplacers.setCheckable(True)
        self.mFileImportReplacers.setShortcut("Ctrl+I")

        self.mEdit = self.menuBar().addMenu("&Edit")

        self.mEditDecode = self.mEdit.addAction("&Decode Texture")
        self.mEditDecode.triggered.connect(self.onClickEditDecode)
        self.mEditDecode.setCheckable(True)
        self.mEditDecode.setShortcut("Ctrl+D")

        self.mEditEncode = self.mEdit.addAction("&Encode Texture")
        self.mEditEncode.triggered.connect(self.onClickEditEncode)
        self.mEditEncode.setCheckable(True)
        self.mEditEncode.setShortcut("Ctrl+E")

    def onClickFileOpenMetadata(self):
        last = self.settings.value("File/Path", "")
        file, _ = QFileDialog.getOpenFileName(self, dir=last)
        if file:
            print("[INFO] Metadata:", file)
            self.settings.setValue("File/Path", file)
            self.message.setText(f"({os.path.basename(file)})  {file}")

            dependency = self.decoder.get_dep(file)
            print("[INFO] Dependencies:")
            [print("      ", _) for _ in dependency]

            self.tDependency.setRowCount(len(dependency))
            self.tReplacer.setRowCount(len(dependency))
            for i, x in enumerate(dependency):
                self.tDependency.setItem(i, 0, QTableWidgetItem(x))
                self.tReplacer.setItem(i, 0, QTableWidgetItem(x))

                path = os.path.join(os.path.dirname(file) + "/", x)
                if os.path.exists(path):
                    print("[INFO] Auto-resolved:", path)
                    self.tDependency.setItem(i, 1, QTableWidgetItem(path))
                    self.decoder.extract_dep(x, path)

    def onClickFileImportReplacers(self):
        last = self.settings.value("File/Path", "")
        files, _ = QFileDialog.getOpenFileNames(self, dir=last)
        if files:
            print("[INFO] Replacers:")
            [print("      ", _) for _ in files]

            for i in range(self.tReplacer.rowCount()):
                name = re.split(r"/|_tex", self.tReplacer.item(i, 0).text())[-2].lower()
                match = [_ for _ in files if os.path.splitext(_)[0].endswith(name)]
                self.tReplacer.setItem(i, 1, QTableWidgetItem(match[0]))
                self.encoder.load_replacer(name, match[0])

    def onClickEditDecode(self):
        last = self.settings.value("File/Path", "")
        dir = QFileDialog.getExistingDirectory(self, dir=os.path.dirname(last))
        if dir:
            psd_path = self.decoder.exec(dir + "/")
            msg_box = QMessageBox()
            msg_box.setWindowTitle("Notice")
            msg_box.setText(f"PSD file: {psd_path}")
            msg_box.setIcon(QMessageBox.Icon.Information)
            msg_box.setStandardButtons(
                QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Ok
            )
            if msg_box.exec() == QMessageBox.StandardButton.Open:
                os.startfile(dir)

    def onClickEditEncode(self):
        last = self.settings.value("File/Path", "")
        dir = QFileDialog.getExistingDirectory(self, dir=os.path.dirname(last))
        if dir:
            self.encoder.from_decoder(self.decoder)
            self.encoder.exec(dir + "/")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = AzurLaneTachieHelper()

    apply_stylesheet(app, theme="dark_teal.xml", invert_secondary=True)

    win.show()
    app.exec()
