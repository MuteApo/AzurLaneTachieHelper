import os
import sysconfig

lrelease = os.path.join(sysconfig.get_paths()["scripts"], "pyside6-lrelease.exe")
for lang in os.listdir("i18n"):
    if lang.endswith(".ts"):
        os.system(f"{lrelease} i18n/{lang}")

tpk = os.path.join(sysconfig.get_paths()["purelib"], "UnityPy", "resources", "uncompressed.tpk")
with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
    print(f"tpk={tpk}", file=fh)
