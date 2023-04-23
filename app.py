import os
import sys
from pprint import pprint

from PySide6.QtCore import QSettings, Qt, Slot
from PySide6.QtGui import QAction, QFont, QFontMetrics, QIcon
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
    QSpacerItem,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QDialog,
    QMessageBox,
)
from qt_material import apply_stylesheet

from src.DecodeHelper import DecodeHelper


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

    def _layout_abd(self):  # Layout for Assetbundle Dependencies
        label = QLabel("Assetbundle Dependencies")
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # button = QPushButton("Import")
        # button.clicked.connect(self.onClickDependencyImport)
        # button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        layout_1 = QHBoxLayout()
        layout_1.addWidget(label)
        # layout_1.addWidget(button)
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
        layout.addLayout(self._layout_abd())
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

        self.mEdit = self.menuBar().addMenu("&Edit")
        self.mEditDecode = self.mEdit.addAction("&Decode")
        self.mEditDecode.triggered.connect(self.onClickEditDecode)
        self.mEditDecode.setCheckable(True)
        self.mEditDecode.setShortcut("Ctrl+D")

    def onClickFileOpenMetadata(self):
        last = self.settings.value("File/OpenMetadata_Path", "")
        file, _ = QFileDialog.getOpenFileName(self, dir=last)
        if file:
            print("[INFO] Metadata:", file)
            self.settings.setValue("File/OpenMetadata_Path", file)

            self.decoder = DecodeHelper(file)
            self.message.setText(f"({self.decoder.file})  {self.decoder.path}")

            dependency = self.decoder.get_dep()
            print("[INFO] Dependencies:")
            [print("      ", _) for _ in dependency]

            self.tDependency.setRowCount(len(dependency))
            for i, x in enumerate(dependency):
                self.tDependency.setItem(i, 0, QTableWidgetItem(x))
                path = os.path.join(os.path.dirname(file) + "/", x)
                if os.path.exists(path):
                    print("[INFO] Auto-resolved:", path)
                    self.tDependency.setItem(i, 1, QTableWidgetItem(path))
                    self.decoder.extract_dep(x, path)

    def onClickEditDecode(self):
        last = self.settings.value("File/OpenMetadata_Path", "")
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
            btn = msg_box.exec()
            if btn == QMessageBox.StandardButton.Open:
                os.startfile(dir)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = AzurLaneTachieHelper()

    apply_stylesheet(app, theme="dark_teal.xml", invert_secondary=True)

    win.show()
    app.exec()
