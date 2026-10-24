from pathlib import Path
from typing import override

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import QComboBox, QDialogButtonBox, QTableWidget, QTableWidgetItem

from domain.model import Kind
from ui.widgets.chrome import WorkbenchDialog, error_dialog
from ui.widgets.controls import label


class ImportDialog(WorkbenchDialog):
    """Every selected image is visible, including ambiguous and unmatched names."""

    def __init__(self, session, paths: list[Path], parent=None):
        super().__init__(parent)
        self.setWindowTitle(QCoreApplication.translate("Dialogs", "Choose replacement images"))
        self.resize(780, 460)
        self.paths = paths
        self.combos: list[QComboBox] = []
        layout = self.body
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        note = label(
            QCoreApplication.translate(
                "Dialogs",
                "Names are matched for you. Check the choices below; you can undo replacements later.",
            )
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        table = QTableWidget(len(paths), 2)
        table.setHorizontalHeaderLabels(
            [
                QCoreApplication.translate("Dialogs", "Image file"),
                QCoreApplication.translate("Dialogs", "Replace this layer"),
            ]
        )
        table.verticalHeader().hide()
        table.horizontalHeader().setStretchLastSection(True)
        table.setColumnWidth(0, 320)
        matches = session.match_images(paths)
        for row, path in enumerate(paths):
            item = QTableWidgetItem(path.name)
            item.setToolTip(str(path))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row, 0, item)
            combo = QComboBox()
            combo.addItem(QCoreApplication.translate("Dialogs", "Skip this image"), None)
            for asset in session.project.assets:
                kind = {
                    Kind.PAINTING: QCoreApplication.translate("Dialogs", "Artwork"),
                    Kind.FACE: QCoreApplication.translate("Dialogs", "Expression"),
                    Kind.ICON: QCoreApplication.translate("Dialogs", "Portraits"),
                }[asset.kind]
                combo.addItem(f"{kind} / {asset.name}", asset.key)
            candidates = matches.get(path, [])
            if len(candidates) == 1:
                combo.setCurrentIndex(combo.findData(candidates[0]))
            self.combos.append(combo)
            table.setCellWidget(row, 1, combo)
            table.setRowHeight(row, 43)
        layout.addWidget(table)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primary")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            QCoreApplication.translate("Dialogs", "Apply replacements")
        )
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            QCoreApplication.translate("Dialogs", "Cancel")
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def mapping(self) -> dict[str, Path]:
        return {
            combo.currentData(): path
            for path, combo in zip(self.paths, self.combos)
            if combo.currentData() is not None
        }

    @override
    def accept(self) -> None:
        keys = [combo.currentData() for combo in self.combos if combo.currentData() is not None]
        if len(keys) != len(set(keys)):
            error_dialog(
                self,
                QCoreApplication.translate(
                    "Dialogs", "Multiple images target the same layer. Select only one image per layer."
                ),
            )
            return
        if not keys:
            error_dialog(self, QCoreApplication.translate("Dialogs", "Select at least one target layer."))
            return
        super().accept()
