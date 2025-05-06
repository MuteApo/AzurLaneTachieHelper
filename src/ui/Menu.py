import os
from functools import partial
from typing import Callable

import UnityPy
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu
from UnityPy.classes import MonoBehaviour
from UnityPy.enums import ClassIDType

from ..base import Config
from ..base.Data import FaceModeType
from ..logger import logger
from ..module.AdbHelper import AdbHelper
from ..ui.TachiePuller import TachiePuller


def pull_tachie():
    if not os.path.exists("dependencies"):
        AdbHelper.pull("dependencies", add_prefix=True)
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
        self.aPullDeps = QAction(
            self.tr("Pull Dependencies"),
            shortcut="Ctrl+Z",
            enabled=True,
            triggered=lambda: AdbHelper.pull("dependencies", add_prefix=True),
        )
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
    def __init__(self, cb: Callable):
        super().__init__()
        self.setTitle(self.tr("Server"))

        self.cb = cb
        self.aCN = QAction(self.tr("CN"), checkable=True, triggered=partial(self.toggle, server="CN"))
        self.aJP = QAction(self.tr("JP"), checkable=True, triggered=partial(self.toggle, server="JP"))
        self.aEN = QAction(self.tr("EN"), checkable=True, triggered=partial(self.toggle, server="EN"))

        self.addActions([self.aCN, self.aJP, self.aEN])
        self.flush()

    def is_server(self, server: str):
        return Config.get_server() == server

    def toggle(self, _: bool, server: str):
        Config.set_server(server)
        logger.attr(server, f"'{Config.get_package()}'")
        self.flush()

    def flush(self):
        self.aCN.setChecked(self.is_server("CN"))
        self.aJP.setChecked(self.is_server("JP"))
        self.aEN.setChecked(self.is_server("EN"))
        self.cb()


class FaceMode(QMenu):
    def __init__(self, *cbs: list[Callable]):
        super().__init__()
        self.setTitle(self.tr("Paintingface Mode"))

        self.cbs = cbs
        self.aOff = QAction(self.tr("Off"), checkable=True, triggered=partial(self.toggle, mode=FaceModeType.Off))
        self.aAdaptive = QAction(self.tr("Adaptive"), checkable=True, triggered=partial(self.toggle, mode=FaceModeType.Adaptive))
        self.aMax = QAction(self.tr("Maximum"), checkable=True, triggered=partial(self.toggle, mode=FaceModeType.Maximum))

        self.addActions([self.aOff, self.aAdaptive, self.aMax])
        self.flush()

    def toggle(self, _: bool, mode: FaceModeType):
        Config.set_face_mode(mode)
        self.cbs[0](mode != FaceModeType.Off)
        self.flush()

    def flush(self):
        mode = Config.get_face_mode()
        self.aOff.setChecked(mode.is_off())
        self.aAdaptive.setChecked(mode.is_adaptive())
        self.aMax.setChecked(mode.is_maximum())
        self.cbs[1]()


class Option(QMenu):
    def __init__(self, *cbs: list[Callable]):
        super().__init__()
        self.setTitle(self.tr("Option"))

        self.aFaceMode = FaceMode(*cbs)
        self.mServer = Server(cbs[1])

        self.addMenu(self.aFaceMode)
        self.addSeparator()
        self.addMenu(self.mServer)
