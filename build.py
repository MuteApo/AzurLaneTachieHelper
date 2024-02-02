import os
import sysconfig

data = {
    "tpk": [
        os.path.join(sysconfig.get_paths()["purelib"], "UnityPy", "resources"),
        "UnityPy/resources",
    ],
    "i18n": ["i18n/*.qm", "i18n/"],
}

os.system(
    f"nuitka app.py \
    --standalone \
    --enable-plugin=pyside6 \
    --nofollow-import-to=tkinter \
    --windows-icon-from-ico=ico/cheshire.ico \
    --include-data-dir={'='.join(data['tpk'])} \
    --include-data-files={'='.join(data['i18n'])} \
    --output-filename=AzurLaneTachieHelper \
    --output-dir=out"
)
