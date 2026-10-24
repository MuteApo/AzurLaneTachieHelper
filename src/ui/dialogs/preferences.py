from typing import override

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QComboBox, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit

from ui.widgets.chrome import WorkbenchDialog
from ui.widgets.controls import button, label


class PreferencesDialog(WorkbenchDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle(QCoreApplication.translate("Dialogs", "Preferences"))
        self.setMinimumWidth(600)
        self.settings = settings
        self.fields: dict[str, QLineEdit] = {}
        layout = self.body
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(label(QCoreApplication.translate("Dialogs", "Resources & tools"), "heading"))
        form = QFormLayout()
        self.language = QComboBox()
        self.language.addItem(QCoreApplication.translate("Dialogs", "Follow system"), "system")
        self.language.addItem("简体中文", "zh_CN")
        self.language.addItem("English", "en")
        self.language.setCurrentIndex(self.language.findData(settings.get("language", "system")))
        form.addRow(QCoreApplication.translate("Dialogs", "Interface language"), self.language)
        language_note = label(
            QCoreApplication.translate("Dialogs", "Language changes take effect next time you start the app.")
        )
        language_note.setWordWrap(True)
        form.addRow(language_note)
        for key, title in [
            ("manifest_path", QCoreApplication.translate("Dialogs", "Dependency index")),
            ("adb_path", QCoreApplication.translate("Dialogs", "ADB executable")),
        ]:
            row = QHBoxLayout()
            value = str(settings.get(key, ""))
            field = QLineEdit("" if key == "adb_path" and value == "adb" else value)
            field.setPlaceholderText(
                QCoreApplication.translate("Dialogs", "Discover automatically")
                if key == "manifest_path"
                else QCoreApplication.translate("Dialogs", "Automatic — ADB is included")
            )
            field.setClearButtonEnabled(True)
            self.fields[key] = field
            row.addWidget(field)
            row.addWidget(
                button(
                    QCoreApplication.translate("Dialogs", "Browse…"),
                    lambda checked=False, target=field: self._browse(target),
                )
            )
            form.addRow(title, row)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName("primary")
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(
            QCoreApplication.translate("Dialogs", "Save")
        )
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            QCoreApplication.translate("Dialogs", "Cancel")
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self, target):
        path, _ = QFileDialog.getOpenFileName(
            self, QCoreApplication.translate("Dialogs", "Choose a file"), target.text()
        )
        if path:
            target.setText(path)

    @override
    def accept(self) -> None:
        for key, field in self.fields.items():
            self.settings.set(key, field.text().strip())
        self.settings.set("language", self.language.currentData())
        super().accept()
