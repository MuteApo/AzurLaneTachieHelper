from typing import Callable

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

from ..base import Config


class File(QMenu):
    def __init__(self, *cbs: list[Callable]):
        super().__init__()
        self.setTitle(self.tr("File"))

        self.aOpenMetadata = QAction(self.tr("Open Metadata"), shortcut="Ctrl+W", enabled=True, triggered=cbs[0])
        self.aImportPainting = QAction(self.tr("Import Painting"), shortcut="Ctrl+Q", enabled=False, triggered=cbs[1])
        self.aImportFaces = QAction(self.tr("Import Paintingface"), shortcut="Ctrl+A", enabled=False, triggered=cbs[2])
        self.aImportIcons = QAction(self.tr("Import Icons"), shortcut="Ctrl+Z", enabled=False, triggered=cbs[3])
        self.aPullDependency = QAction(self.tr("Pull Dependencies"), shortcut="Ctrl+X", enabled=True, triggered=cbs[4])

        self.addAction(self.aOpenMetadata)
        self.addAction(self.aImportPainting)
        self.addAction(self.aImportFaces)
        self.addAction(self.aImportIcons)
        self.addSeparator()
        self.addAction(self.aPullDependency)


class Edit(QMenu):
    def __init__(self, *cbs: list[Callable]):
        super().__init__()
        self.setTitle(self.tr("Edit"))

        self.aClipIcons = QAction(self.tr("Clip Icons"), shortcut="Ctrl+C", enabled=False, triggered=cbs[0])
        self.aDecodeTexture = QAction(self.tr("Decode Texture"), shortcut="Ctrl+D", enabled=False, triggered=cbs[1])
        self.aEncodeTexture = QAction(self.tr("Encode Texture"), shortcut="Ctrl+E", enabled=False, triggered=cbs[2])

        self.addAction(self.aClipIcons)
        self.addAction(self.aDecodeTexture)
        self.addAction(self.aEncodeTexture)


class Option(QMenu):
    def __init__(self, cb: Callable):
        super().__init__()
        self.setTitle(self.tr("Option"))

        self.aDumpLayer = QAction(
            self.tr("Dump Intermediate Layers"),
            checkable=True,
            checked=Config.get("system", "DumpLayer"),
            triggered=cb,
        )
        self.aAdvMode = QAction(
            self.tr("Advanced Paintingface Mode"),
            checkable=True,
            checked=Config.get("system", "AdvancedMode"),
            triggered=cb,
        )

        self.addAction(self.aDumpLayer)
        self.addAction(self.aAdvMode)
