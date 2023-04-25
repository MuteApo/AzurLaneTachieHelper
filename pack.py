import os
import sys

tpk = sys.exec_prefix + "\\Lib\\site-packages\\UnityPy\\resources"
os.system(
    f"nuitka app.py \
    --onefile \
    --mingw64 \
    --lto=yes \
    --disable-console \
    --enable-plugin=pyside6 \
    --nofollow-import-to=tkinter \
    --windows-icon-from-ico=ico/cheshire.ico \
    --include-data-dir={tpk}=UnityPy\\resources \
    --output-filename=AzurLaneTachieHelper \
    --output-dir=out"
)
