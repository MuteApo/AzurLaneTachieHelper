import ctypes
import locale
import os
import sys

import qdarktheme
from PySide6.QtCore import QTranslator
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from src.TachieHelper import AzurLaneTachieHelper

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("ico/cheshire.ico"))
    qdarktheme.setup_theme("auto")

    if sys.platform == "win32":
        code = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        lang = locale.windows_locale[code]
    else:
        lang = locale.getlocale()[0]

    path = os.path.join("i18n", f"{lang}.qm")
    if os.path.exists(path):
        trans = QTranslator(app)
        trans.load(path)
        app.installTranslator(trans)

    win = AzurLaneTachieHelper()
    win.show()

    sys.exit(app.exec())
