from typing import Callable

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

from ..Config import Config


class File(QMenu):
    def __init__(self, callbacks: dict[str, Callable]):
        super().__init__()
        self.setTitle(self.tr("File"))

        self.aOpenMetadata = QAction(
            self.tr("Open Metadata"),
            self,
            shortcut="Ctrl+M",
            enabled=True,
            triggered=callbacks["Open Metadata"],
        )
        self.aImportPainting = QAction(
            self.tr("Import Painting"),
            self,
            shortcut="Ctrl+P",
            enabled=False,
            triggered=callbacks["Import Painting"],
        )
        self.aImportPaintingface = QAction(
            self.tr("Import Paintingface"),
            self,
            shortcut="Ctrl+F",
            enabled=False,
            triggered=callbacks["Import Paintingface"],
        )
        self.aImportIcons = QAction(
            self.tr("Import Icons"),
            self,
            shortcut="Ctrl+I",
            enabled=False,
            triggered=callbacks["Import Icons"],
        )

        self.addAction(self.aOpenMetadata)
        self.addAction(self.aImportPainting)
        self.addAction(self.aImportPaintingface)
        self.addAction(self.aImportIcons)


class Edit(QMenu):
    def __init__(self, callbacks: dict[str, Callable]):
        super().__init__()
        self.setTitle(self.tr("Edit"))

        self.aClipIcons = QAction(
            self.tr("Clip Icons"),
            self,
            shortcut="Ctrl+C",
            enabled=False,
            triggered=callbacks["Clip Icons"],
        )
        self.aDecodeTexture = QAction(
            self.tr("Decode Texture"),
            self,
            shortcut="Ctrl+D",
            enabled=False,
            triggered=callbacks["Decode Texture"],
        )
        self.aEncodeTexture = QAction(
            self.tr("Encode Texture"),
            self,
            shortcut="Ctrl+E",
            enabled=False,
            triggered=callbacks["Encode Texture"],
        )

        self.addAction(self.aClipIcons)
        self.addAction(self.aDecodeTexture)
        self.addAction(self.aEncodeTexture)


class Option(QMenu):
    def __init__(self, callbacks: dict[str, Callable], config: Config):
        super().__init__()
        self.setTitle(self.tr("Option"))

        self.aDumpLayer = QAction(
            self.tr("Dump Intermediate Layers"),
            self,
            checkable=True,
            checked=config.get_bool("Edit/DumpLayer"),
            triggered=callbacks["Dump Intermediate Layers"],
        )
        self.aAdvMode = QAction(
            self.tr("Advanced Paintingface Mode"),
            self,
            checkable=True,
            checked=config.get_bool("Edit/AdvancedMode"),
            triggered=callbacks["Advanced Paintingface Mode"],
        )

        self.addAction(self.aDumpLayer)
        self.addAction(self.aAdvMode)
