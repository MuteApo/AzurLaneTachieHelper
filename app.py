import ctypes
import locale
import os
import subprocess
import sys
from ast import literal_eval

import qdarktheme
import UnityPy.config
from PySide6.QtCore import QTranslator
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from src.TachieHelper import AzurLaneTachieHelper

UnityPy.config.FALLBACK_UNITY_VERSION = "2022.3.62f3"

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("ico/cheshire.ico"))
    qdarktheme.setup_theme("auto")

    if sys.platform == "win32":
        code = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        lang = locale.windows_locale[code]
    elif sys.platform == "darwin":
        cmd = ["defaults", "read", "-g", "AppleLanguages"]
        output = subprocess.check_output(cmd, text=True)
        lang = literal_eval(output)[0]
        if lang == "zh-Hans-CN":
            lang = "zh_CN"
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
