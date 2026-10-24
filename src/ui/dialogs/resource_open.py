"""Find familiar resource layouts without decoding Unity bundles during selection."""

import re
from pathlib import Path
from typing import override

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import QDialog, QFileDialog, QHBoxLayout, QHeaderView, QTreeWidget, QTreeWidgetItem

from ui.widgets.chrome import WorkbenchDialog
from ui.widgets.controls import button, label

_DEPENDENCY_FOLDERS = {"paintingface", "shipyardicon", "herohrzicon", "squareicon", "ui"}
_RESERVED_FILES = {"dependencies", "custom_builtin", "catalog", "manifest"}
_TEXTURE_NAME = re.compile(r"(?:^|_)(?:tex(?:ture)?\d*|atlas)(?:_|$)", re.IGNORECASE)


def _resource_file(path: Path) -> bool:
    return (
        path.is_file()
        and not path.suffix
        and not path.name.startswith(".")
        and path.name.casefold() not in _RESERVED_FILES
        and _TEXTURE_NAME.search(path.name) is None
    )


def discover_resources(folder: Path) -> list[Path]:
    """Recognize saved work, legacy project/name, and project/painting/name layouts.

    Only the selected folder and its immediate project folders are considered. Root-level
    extensionless files need a matching project name or a paired normal variant; arbitrary
    dependency bundles are never offered simply because they have no extension.
    """
    folder = folder.resolve()
    found: set[Path] = set()

    def scan(project: Path):
        entries = list(project.iterdir())
        found.update(p for p in entries if p.is_file() and p.name.lower().endswith(".tachie.json"))
        if project.name.casefold() in _DEPENDENCY_FOLDERS:
            return
        if project.name.casefold() == "painting":
            found.update(p for p in entries if _resource_file(p))
            return
        named = {p.name.casefold(): p for p in entries if _resource_file(p)}
        for name in (project.name.casefold(), project.name.casefold() + "_n"):
            if name in named:
                found.add(named[name])
        # Old projects are often copied into a renamed working folder.
        for name, path in named.items():
            if name.endswith("_n") and name[:-2] in named:
                found.update((path, named[name[:-2]]))
        painting = project / "painting"
        if painting.is_dir():
            found.update(p for p in painting.iterdir() if _resource_file(p))

    scan(folder)
    if folder.name.casefold() not in _DEPENDENCY_FOLDERS | {"painting"}:
        for child in folder.iterdir():
            if (
                child.is_dir()
                and not child.name.startswith(".")
                and child.name.casefold() not in _DEPENDENCY_FOLDERS | {"painting"}
            ):
                scan(child)
    return sorted(found, key=lambda p: (not p.name.lower().endswith(".tachie.json"), str(p).casefold()))


class OpenResourceDialog(WorkbenchDialog):
    def __init__(self, parent=None, folder: Path | None = None):
        super().__init__(parent)
        self.selected_path: Path | None = None
        self.folder = folder
        self.candidates: list[Path] = []
        self.setWindowTitle(QCoreApplication.translate("Opening", "Open artwork"))
        self.resize(760, 460)
        layout = self.body
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        choices = QHBoxLayout()
        choices.addWidget(
            button(QCoreApplication.translate("Opening", "Choose resource folder…"), self.choose_folder, True)
        )
        choices.addWidget(
            button(
                QCoreApplication.translate("Opening", "Open saved work or resource file…"), self.choose_file
            )
        )
        choices.addStretch()
        layout.addLayout(choices)
        self.location = label("")
        self.location.setWordWrap(True)
        self.location.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.location)
        self.feedback = label("")
        self.feedback.setWordWrap(True)
        self.feedback.hide()
        layout.addWidget(self.feedback)
        self.list = QTreeWidget()
        self.list.setRootIsDecorated(False)
        self.list.setAlternatingRowColors(True)
        self.list.setHeaderLabels(
            [
                QCoreApplication.translate("Opening", "Artwork"),
                QCoreApplication.translate("Opening", "Type"),
                QCoreApplication.translate("Opening", "Location"),
            ]
        )
        self.list.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.list.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.list.header().setStretchLastSection(True)
        self.list.itemSelectionChanged.connect(self._selection_changed)
        self.list.itemDoubleClicked.connect(self.accept)
        layout.addWidget(self.list, 1)
        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(button(QCoreApplication.translate("Opening", "Cancel"), self.reject))
        self.open_button = button(
            QCoreApplication.translate("Opening", "Open selected artwork"), self.accept, True
        )
        self.open_button.setEnabled(False)
        actions.addWidget(self.open_button)
        layout.addLayout(actions)
        if folder is not None:
            self.set_folder(folder)

    def set_folder(self, folder: Path):
        self.folder = folder.resolve()
        self.feedback.show()
        self.location.setText(str(self.folder))
        self.list.clear()
        self.selected_path = None
        try:
            self.candidates = discover_resources(self.folder)
        except OSError as error:
            self.candidates = []
            self.feedback.setText(str(error))
            return
        for path in self.candidates:
            saved = path.name.lower().endswith(".tachie.json")
            name = path.name[: -len(".tachie.json")] if saved else path.name
            kind = (
                QCoreApplication.translate("Opening", "Saved work")
                if saved
                else QCoreApplication.translate("Opening", "Game resource")
            )
            item = QTreeWidgetItem([name, kind, str(path.relative_to(self.folder))])
            item.setData(0, Qt.ItemDataRole.UserRole, path)
            item.setToolTip(2, str(path))
            self.list.addTopLevelItem(item)
        if self.candidates:
            self.feedback.setText(QCoreApplication.translate("Opening", "Choose the artwork to open."))
            if len(self.candidates) == 1:
                first = self.list.topLevelItem(0)
                if first is not None:
                    self.list.setCurrentItem(first)
        else:
            self.feedback.setText(
                QCoreApplication.translate(
                    "Opening",
                    "No artwork found here. Choose the folder you extracted or pulled from the game, or use Open saved work or resource file.",
                )
            )

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, QCoreApplication.translate("Opening", "Choose resource folder"), str(self.folder or "")
        )
        if folder:
            self.set_folder(Path(folder))
            if len(self.candidates) == 1:
                self.accept()

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            QCoreApplication.translate("Opening", "Open saved work or resource file"),
            str(self.folder or ""),
            QCoreApplication.translate(
                "Opening", "Saved work and resources (*.tachie.json *);;All files (*)"
            ),
        )
        if path:
            self.selected_path = Path(path)
            super().accept()

    def _selection_changed(self):
        self.open_button.setEnabled(bool(self.list.selectedItems()))

    @override
    def accept(self) -> None:
        selected = self.list.selectedItems()
        if selected:
            self.selected_path = selected[0].data(0, Qt.ItemDataRole.UserRole)
            super().accept()


def choose_resource(parent=None, folder: Path | None = None) -> Path | None:
    dialog = OpenResourceDialog(parent, folder)
    try:
        if folder is not None and len(dialog.candidates) == 1:
            return dialog.candidates[0]
        return dialog.selected_path if dialog.exec() == QDialog.DialogCode.Accepted else None
    finally:
        dialog.deleteLater()
