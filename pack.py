import os
import sysconfig
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("-n", "--nuitka", action="store_true", help="packed by nuitka")
parser.add_argument("-p", "--pyinstaller", action="store_true", help="packed by pyinstaller")

dst = os.path.join("UnityPy", "resources")
src = os.path.join(sysconfig.get_paths()["purelib"], dst)

if __name__ == "__main__":
    args = parser.parse_args()

    if "nuitka" in args:
        os.system(
            f"nuitka app.py \
            --standalone \
            --lto=yes \
            --disable-console \
            --enable-plugin=pyside6 \
            --nofollow-import-to=tkinter \
            --windows-icon-from-ico=ico/cheshire.ico \
            --include-data-dir={src}={dst} \
            --output-filename=AzurLaneTachieHelper \
            --output-dir=out"
        )
    else:
        os.system(
            f"pyinstaller -Dwy app.py \
            --name AzurLaneTachieHelper \
            --icon ico/cheshire.ico \
            --add-data {src};{dst}"
        )
