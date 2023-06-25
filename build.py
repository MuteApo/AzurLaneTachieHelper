import os
import sysconfig
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("-n", "--nuitka", action="store_true", help="packed by nuitka")
parser.add_argument("-p", "--pyinstaller", action="store_true", help="packed by pyinstaller")

data = {
    "tpk": [
        os.path.join(sysconfig.get_paths()["purelib"], "UnityPy", "resources"),
        os.path.join("UnityPy", "resources"),
    ],
    "i18n": ["i18n", "i18n"],
}

if __name__ == "__main__":
    args = parser.parse_args()

    if args.nuitka:
        os.system(
            f"nuitka app.py \
            --standalone \
            --enable-plugin=pyside6 \
            --nofollow-import-to=tkinter \
            --windows-icon-from-ico=ico/cheshire.ico \
            --include-data-dir={'='.join(data['tpk'])} \
            --include-data-dir={'='.join(data['i18n'])} \
            --output-filename=AzurLaneTachieHelper \
            --output-dir=out"
        )
    elif args.pyinstaller:
        os.system(
            f"pyinstaller -Dcy app.py \
            --name AzurLaneTachieHelper \
            --icon ico/cheshire.ico \
            --add-data {';'.join(data['tpk'])} \
            --add-data {';'.join(data['i18n'])}"
        )
