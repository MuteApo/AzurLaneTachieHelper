# -*- mode: python ; coding: utf-8 -*-
import itertools
import os
import sysconfig

dst = os.path.join("UnityPy", "resources")
src = os.path.join(sysconfig.get_paths()["purelib"], dst)
tpk = Tree(root=src, prefix=dst, typecode="DATA")

block_cipher = None


def gen_a(script, target):
    a = Analysis([script], cipher=block_cipher)
    return a, script.split(".")[0], target


def gen_exe(a, _, target):
    pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=target,
        debug=False,
        strip=False,
        upx=True,
        console=True,
        icon=["ico\\cheshire.ico"],
    )

    return exe, a.binaries, a.zipfiles, a.datas


app = [
    ("decoder.py", "AzurLaneTachieDecoder"),
    ("encoder.py", "AzurLaneTachieEncoder"),
    ("merger.py", "AzurLaneTachieMerger"),
    ("splitter.py", "AzurLaneTachieSplitter"),
    ("viewer.py", "AzurLaneTachieViewer"),
]

analysis_list = [gen_a(*_) for _ in app]
MERGE(*analysis_list)

info = itertools.chain(*[gen_exe(*_) for _ in analysis_list])
coll = COLLECT(
    *info,
    tpk,
    strip=False,
    upx=True,
    name="AzurLaneTachieHelper",
)
