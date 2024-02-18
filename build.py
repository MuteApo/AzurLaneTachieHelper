import argparse
import os
import sysconfig

tpk_folder = os.path.join(sysconfig.get_paths()["purelib"], "UnityPy", "resources")
data = {
    "tpk": [tpk_folder, "UnityPy/resources/"],
    "i18n": ["i18n/*.qm", "i18n/"],
}

for lang in os.listdir("i18n"):
    if lang.endswith(".ts"):
        os.system(f"pyside6-lrelease i18n/{lang}")

parser = argparse.ArgumentParser()
parser.add_argument("--prepare", action="store_true")

if __name__ == "__main__":
    args = parser.parse_args()
    if args.prepare:
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            print(f"tpk_folder={tpk_folder}", file=fh)
    else:
        os.system(
            f"nuitka app.py \
            --standalone \
            --mingw64 \
            --enable-plugin=pyside6 \
            --nofollow-import-to=tkinter \
            --windows-icon-from-ico=ico/cheshire.ico \
            --include-data-dir={'='.join(data['tpk'])} \
            --include-data-files={'='.join(data['i18n'])} \
            --output-file=AzurLaneTachieHelper"
        )
