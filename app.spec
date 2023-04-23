# -*- mode: python ; coding: utf-8 -*-
import itertools
import os
import sysconfig

dst = os.path.join("UnityPy", "resources")
src = os.path.join(sysconfig.get_paths()["purelib"], dst)
tpk = Tree(root=src, prefix=dst, typecode="DATA")

block_cipher = None


a = Analysis(["app.py"], cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AzurLaneTachieHelper",
    debug=False,
    strip=False,
    upx=True,
    console=False,
    icon=["ico\\cheshire.ico"],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    tpk,
    strip=False,
    upx=True,
    name="AzurLaneTachieHelper",
)
