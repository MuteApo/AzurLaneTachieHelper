from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLineEdit, QTableWidget, QTableWidgetItem, QToolButton

from ui.widgets.chrome import WorkbenchDialog
from ui.widgets.controls import button, label


class ExportDialog(WorkbenchDialog):
    """Choose an output location first; technical changes remain available on demand."""

    def __init__(self, project, directory: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(QCoreApplication.translate("Dialogs", "Export game files"))
        self.setMinimumWidth(680)
        self.resize(720, 340)
        layout = self.body
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(label(QCoreApplication.translate("Dialogs", "Save exported files to"), "heading"))
        row = QHBoxLayout()
        self.directory = QLineEdit(directory)
        self.directory.setPlaceholderText(QCoreApplication.translate("Dialogs", "Choose an output folder"))
        row.addWidget(self.directory)
        row.addWidget(button(QCoreApplication.translate("Dialogs", "Browse…"), self._browse))
        layout.addLayout(row)
        layout.addWidget(
            label(QCoreApplication.translate("Dialogs", "Changed layers: {0}").format(len(project.modified)))
        )
        self.details_button = QToolButton()
        self.details_button.setText(QCoreApplication.translate("Dialogs", "Review changes"))
        self.details_button.setCheckable(True)
        self.details_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.details_button.setArrowType(Qt.ArrowType.RightArrow)
        layout.addWidget(self.details_button, 0, Qt.AlignmentFlag.AlignLeft)
        table = QTableWidget(len(project.modified), 3)
        self.details = table
        table.setHorizontalHeaderLabels(
            [
                QCoreApplication.translate("Dialogs", "Layer"),
                QCoreApplication.translate("Dialogs", "Bundle"),
                QCoreApplication.translate("Dialogs", "Output size"),
            ]
        )
        table.verticalHeader().hide()
        table.horizontalHeader().setStretchLastSection(True)
        table.setColumnWidth(0, 180)
        table.setColumnWidth(1, 200)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setMinimumHeight(160)
        table.setMaximumHeight(240)
        for row, asset in enumerate(project.modified):
            image = asset.image()
            for col, text in enumerate(
                (asset.name, asset.texture.bundle.name, f"{image.width} × {image.height}")
            ):
                table.setItem(row, col, QTableWidgetItem(text))
            table.setRowHeight(row, 36)
        layout.addWidget(table)
        table.hide()
        self.details_button.toggled.connect(self._show_details)
        note = label(QCoreApplication.translate("Dialogs", "To continue editing later, use Save work."))
        note.setWordWrap(True)
        layout.addWidget(note)
        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(button(QCoreApplication.translate("Dialogs", "Cancel"), self.reject))
        self.export_button = button(
            QCoreApplication.translate("Dialogs", "Export game files"), self.accept, True
        )
        self.export_button.setEnabled(bool(directory))
        self.directory.textChanged.connect(lambda text: self.export_button.setEnabled(bool(text.strip())))
        actions.addWidget(self.export_button)
        layout.addLayout(actions)

    def _show_details(self, visible: bool):
        self.details.setVisible(visible)
        self.details_button.setArrowType(Qt.ArrowType.DownArrow if visible else Qt.ArrowType.RightArrow)
        self.adjustSize()

    def _browse(self):
        path = QFileDialog.getExistingDirectory(
            self, QCoreApplication.translate("Dialogs", "Choose an output folder"), self.directory.text()
        )
        if path:
            self.directory.setText(path)
