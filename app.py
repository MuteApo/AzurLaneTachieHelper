import locale
import os
import sys

from PySide6.QtCore import QTranslator
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from src.TachieHelper import AzurLaneTachieHelper

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("ico/cheshire.ico"))

    path = os.path.join("i18n", locale.getdefaultlocale()[0] + ".qm")
    if os.path.exists(path):
        trans = QTranslator(app)
        trans.load(path)
        app.installTranslator(trans)

    win = AzurLaneTachieHelper()
    win.show()

    sys.exit(app.exec())
