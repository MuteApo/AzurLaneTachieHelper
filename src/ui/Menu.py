import os
import re
import threading
from functools import partial
from typing import Callable

import numpy as np
import UnityPy
from PIL import Image
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu
from UnityPy.classes import GameObject, MonoBehaviour, RectTransform, Texture2D
from UnityPy.enums import ClassIDType

from ..base import Config
from ..logger import logger
from ..module import AdbHelper
from ..ui import TachiePuller


def pull_deps():
    AdbHelper.connect()
    for line in AdbHelper.devices():
        addr, name = line.split("\t")
        logger.attr(name, addr)
    AdbHelper.pull("dependencies")


def pull_tachie():
    assert os.path.exists("dependencies"), f"AssetBundles/dependencies not found"
    env = UnityPy.load("dependencies")
    mb: MonoBehaviour = [x.read() for x in env.objects if x.type == ClassIDType.MonoBehaviour][0]
    data = {k: v.m_Dependencies for k, v in zip(mb.m_Keys, mb.m_Values) if k.startswith("painting/")}
    puller = TachiePuller(data)
    if puller.exec():
        pass


class File(QMenu):
    def __init__(self, *cbs: list[Callable]):
        super().__init__()
        self.setTitle(self.tr("File"))

        self.aOpenMetadata = QAction(self.tr("Open Metadata"), shortcut="Ctrl+S", enabled=True, triggered=cbs[0])
        self.aImportPainting = QAction(self.tr("Import Painting"), shortcut="Ctrl+W", enabled=False, triggered=cbs[1])
        self.aImportFaces = QAction(self.tr("Import Paintingface"), shortcut="Ctrl+Q", enabled=False, triggered=cbs[2])
        self.aImportIcons = QAction(self.tr("Import Icons"), shortcut="Ctrl+A", enabled=False, triggered=cbs[3])
        self.aPullDeps = QAction(self.tr("Pull Dependencies"), shortcut="Ctrl+Z", enabled=True, triggered=pull_deps)
        self.aPullTachie = QAction(self.tr("Pull Tachie"), shortcut="Ctrl+X", enabled=True, triggered=pull_tachie)

        self.addActions([self.aOpenMetadata, self.aImportPainting, self.aImportFaces, self.aImportIcons])
        self.addSeparator()
        self.addActions([self.aPullDeps, self.aPullTachie])


class Edit(QMenu):
    def __init__(self, *cbs: list[Callable]):
        super().__init__()
        self.setTitle(self.tr("Edit"))

        self.aClipIcons = QAction(self.tr("Clip Icons"), shortcut="Ctrl+C", enabled=False, triggered=cbs[0])
        self.aDecodeTexture = QAction(self.tr("Decode Texture"), shortcut="Ctrl+D", enabled=False, triggered=cbs[1])
        self.aEncodeTexture = QAction(self.tr("Encode Texture"), shortcut="Ctrl+E", enabled=False, triggered=cbs[2])

        self.addActions([self.aClipIcons, self.aDecodeTexture, self.aEncodeTexture])


class Server(QMenu):
    def __init__(self):
        super().__init__()
        self.setTitle(self.tr("Server"))

        self.aCN = QAction(self.tr("CN Server"), checkable=True, triggered=partial(self.toggle, server="CN"))
        self.aJP = QAction(self.tr("JP Server"), checkable=True, triggered=partial(self.toggle, server="JP"))
        self.aEN = QAction(self.tr("EN Server"), checkable=True, triggered=partial(self.toggle, server="EN"))

        self.addActions([self.aCN, self.aJP, self.aEN])
        self.flush()

    def is_server(self, server: str):
        return Config.get("system", "Server") == server

    def toggle(self, _: bool, server: str):
        logger.attr(server, f"'{AdbHelper._to_pkg[server]}'")
        Config.set("system", "Server", server)
        self.flush()

    def flush(self):
        self.aCN.setChecked(self.is_server("CN"))
        self.aJP.setChecked(self.is_server("JP"))
        self.aEN.setChecked(self.is_server("EN"))


class Option(QMenu):
    def __init__(self, cb: Callable):
        super().__init__()
        self.setTitle(self.tr("Option"))

        self.aAdvMode = QAction(
            self.tr("Advanced Paintingface Mode"),
            checkable=True,
            checked=Config.get("system", "AdvancedMode"),
            triggered=cb,
        )
        self.mServer = Server()

        self.addAction(self.aAdvMode)
        self.addSeparator()
        self.addMenu(self.mServer)
