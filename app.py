import os
import sys

from PySide6.QtCore import QSettings, Qt, Slot
from PySide6.QtGui import QAction, QIcon, QFontMetrics, QFont
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QSpacerItem,
)
from qt_material import apply_stylesheet

from src.DecoderHelper import DecodeHelper


class AzurLaneTachieHelper(QMainWindow):
    def __init__(self):
        super(AzurLaneTachieHelper, self).__init__()
        self.setWindowTitle("AzurLaneTachieHelper")
        self.setWindowIcon(QIcon("ico/cheshire.ico"))

        self.settings = QSettings("config.ini", QSettings.Format.IniFormat)

        self._init_ui()
        self._init_statusbar()
        self._init_menu()

    def _layout_dependency(self):
        label = QLabel("Dependency List:")
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        button = QPushButton("Import")
        button.clicked.connect(self.onClickDependencyImport)
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        layout_1 = QHBoxLayout()
        layout_1.addWidget(label)
        layout_1.addWidget(button)
        layout_1.addItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        )

        self.tDependency = QTableWidget()
        self.tDependency.setColumnCount(2)
        self.tDependency.setHorizontalHeaderLabels(["Name", "Path"])
        self.tDependency.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.tDependency.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.tDependency.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Expanding
        )

        layout_2 = QHBoxLayout()
        layout_2.addWidget(self.tDependency)

        layout_top = QVBoxLayout()
        layout_top.addLayout(layout_1)
        layout_top.addLayout(layout_2)

        return layout_top

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.addLayout(self._layout_dependency())
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
        self.mFileOpen = self.mFile.addMenu("&Open")
        self.mFileOpenMetadata = self.mFileOpen.addAction("&Metadata")
        self.mFileOpenMetadata.triggered.connect(self.onClickFileOpenMetadata)
        self.mFileOpenMetadata.setCheckable(True)
        self.mFileOpenMetadata.setShortcut("Ctrl+M")

        self.mEdit = self.menuBar().addMenu("&Edit")
        self.mEditExtractAndDecode = self.mEdit.addAction("&Extract And Decode")
        self.mEditExtractAndDecode.triggered.connect(self.onClickEditExtractAndDecode)
        self.mEditExtractAndDecode.setCheckable(True)

    def onClickFileOpenMetadata(self):
        last = self.settings.value("FileOpen/MetaDataPath", "")
        file, _ = QFileDialog.getOpenFileName(self, dir=last)
        if file:
            print("[INFO] Metadata", file)
            self.settings.setValue("FileOpen/MetaDataPath", file)

            self.decoder = DecodeHelper(file)
            self.message.setText(f"({self.decoder.file}) {self.decoder.path}")
            dependency = self.decoder.get_dependency()
            self.tDependency.setRowCount(len(dependency))
            for i, x in enumerate(dependency):
                self.tDependency.setItem(i, 0, QTableWidgetItem(x))
                self.tDependency.setItem(i, 1, QTableWidgetItem("Unknown"))

    def onClickEditExtractAndDecode(self):
        last = self.settings.value(
            "Edit/ExtractDir", self.settings.value("FileOpen/MetaDataPath", "")
        )
        dir = QFileDialog.getExistingDirectory(self, dir=last)
        if dir:
            self.settings.setValue("Edit/ExtractDir", dir)
            self.decoder.extract_dependency(
                [
                    self.tDependency.item(i, 1).text()
                    for i in range(self.tDependency.rowCount())
                ],
                output_dir=dir,
            )
            self.decoder.exec(dir)

    def onClickDependencyImport(self):
        last = self.settings.value(
            "FileOpen/DependencyPath", self.settings.value("FileOpen/MetaDataPath", "")
        )
        files, _ = QFileDialog.getOpenFileNames(
            self, dir=last, filter=f"Texture Assetbundle ({self.decoder.file}*_tex)"
        )
        if files:
            print("[INFO] Dependencies", files)
            self.settings.setValue("FileOpen/DependencyPath", files[-1])

            for i in range(self.tDependency.rowCount()):
                name = self.tDependency.item(i, 0).text().split(".")[-1]
                match = [_ for _ in files if _.endswith(name)]
                if len(match):
                    self.tDependency.setItem(i, 1, QTableWidgetItem(match[0]))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = AzurLaneTachieHelper()

    apply_stylesheet(app, theme="dark_teal.xml", invert_secondary=True)

    win.show()
    app.exec()
