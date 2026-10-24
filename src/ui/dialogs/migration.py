"""Review and import legacy preferences without changing an open editing session."""

import logging
from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QFileDialog, QFormLayout, QHBoxLayout, QLineEdit, QPlainTextEdit

from adapters.legacy import LegacyPreview, apply_legacy, preview_legacy
from adapters.storage import Settings
from ui.i18n import render_message
from ui.widgets.chrome import WorkbenchDialog, error_dialog
from ui.widgets.controls import button, label

logger = logging.getLogger(__name__)


class MigrationDialog(WorkbenchDialog):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.preview: LegacyPreview | None = None
        self.setWindowTitle(QCoreApplication.translate("Migration", "Import legacy settings"))
        self.resize(760, 580)
        layout = self.body
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        note = label(
            QCoreApplication.translate(
                "Migration",
                "Read preferences, icon presets and extension bounds from the legacy INI. Review them before importing.",
            )
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        self.source = QLineEdit(str(Path.home() / "AzurLaneTachieHelper.ini"))
        source_row = QHBoxLayout()
        source_row.addWidget(self.source)
        source_row.addWidget(button(QCoreApplication.translate("Migration", "Browse…"), self._source))
        form.addRow(QCoreApplication.translate("Migration", "Legacy INI"), source_row)
        self.repository = QLineEdit(str(Path(__file__).resolve().parents[3]))
        repository_row = QHBoxLayout()
        repository_row.addWidget(self.repository)
        repository_row.addWidget(button(QCoreApplication.translate("Migration", "Browse…"), self._repository))
        form.addRow(QCoreApplication.translate("Migration", "Legacy working folder"), repository_row)
        layout.addLayout(form)
        hint = label(
            QCoreApplication.translate(
                "Migration",
                "This folder resolves relative paths in legacy settings, such as 3rdparty/adb.exe.",
            )
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setPlaceholderText(
            QCoreApplication.translate(
                "Migration", "Preview to review settings to import and any skipped entries."
            )
        )
        layout.addWidget(self.report, 1)
        self.status = label(
            QCoreApplication.translate(
                "Migration", "Import updates matching preferences and presets. The open project is unchanged."
            )
        )
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        actions = QHBoxLayout()
        actions.addWidget(button(QCoreApplication.translate("Migration", "Close"), self.reject))
        actions.addStretch()
        actions.addWidget(button(QCoreApplication.translate("Migration", "Preview import"), self._preview))
        self.import_button = button(
            QCoreApplication.translate("Migration", "Import reviewed settings"), self._apply, primary=True
        )
        self.import_button.setEnabled(False)
        actions.addWidget(self.import_button)
        layout.addLayout(actions)
        self.source.textChanged.connect(self._invalidate)
        self.repository.textChanged.connect(self._invalidate)

    def _invalidate(self):
        self.preview = None
        self.import_button.setEnabled(False)
        self.report.clear()

    def _source(self):
        value, _ = QFileDialog.getOpenFileName(
            self,
            QCoreApplication.translate("Migration", "Select legacy INI"),
            self.source.text(),
            "INI (*.ini)",
        )
        if value:
            self.source.setText(value)
            self._preview()

    def _repository(self):
        value = QFileDialog.getExistingDirectory(
            self,
            QCoreApplication.translate("Migration", "Select legacy working folder"),
            self.repository.text(),
        )
        if value:
            self.repository.setText(value)

    def _preview(self):
        self._invalidate()
        try:
            preview = preview_legacy(Path(self.source.text()), Path(self.repository.text()))
        except Exception as error:
            logger.exception("Failed to preview legacy settings")
            error_dialog(self, error)
            return
        self.preview = preview
        setting_names = {
            "adb_path": QCoreApplication.translate("Migration", "ADB executable"),
            "recent_projects": QCoreApplication.translate("Migration", "Recent projects"),
            "compression": QCoreApplication.translate("Migration", "Compression"),
            "face_mode": QCoreApplication.translate("Migration", "Face mode"),
            "serial": QCoreApplication.translate("Migration", "Device"),
            "server": QCoreApplication.translate("Migration", "Server"),
            "package_name": QCoreApplication.translate("Migration", "Game package"),
        }
        lines = [QCoreApplication.translate("Migration", "Preferences")]
        for key, value in preview.preferences.items():
            if isinstance(value, bool):
                display = (
                    QCoreApplication.translate("Migration", "Enabled")
                    if value
                    else QCoreApplication.translate("Migration", "Disabled")
                )
            elif isinstance(value, list):
                display = ", ".join(map(str, value))
            else:
                display = str(value)
            lines.append(f"  {setting_names[key]}: {display}")
        for name, defaults in preview.projects.items():
            lines.extend(["", QCoreApplication.translate("Migration", "Project: {name}").format(name=name)])
            for kind, preset in defaults.presets.items():
                lines.append(
                    QCoreApplication.translate(
                        "Migration",
                        "  {kind}: {width} × {height}; center {pivot}; scale {scale}; angle {angle}°",
                    ).format(
                        kind=kind,
                        width=preset.size[0],
                        height=preset.size[1],
                        pivot=preset.pivot,
                        scale=preset.scale,
                        angle=preset.angle,
                    )
                )
            for layer, bounds in defaults.extensions.items():
                lines.append(
                    QCoreApplication.translate(
                        "Migration", "  {layer} extension (left, bottom, right, top): {bounds}"
                    ).format(layer=layer, bounds=bounds)
                )
        if preview.issues:
            lines.extend(["", QCoreApplication.translate("Migration", "These entries were skipped:")])
            lines.extend(f"{issue.key}: {render_message(issue.message)}" for issue in preview.issues)
        if preview.ignored:
            lines.extend(["", QCoreApplication.translate("Migration", "Unused legacy settings:")])
            for key in preview.ignored:
                lines.append(
                    QCoreApplication.translate(
                        "Migration", "{key}: artwork now uses the Unity resource geometry automatically."
                    ).format(key=key)
                    if key == "system/MeshMode"
                    else key
                )
        self.report.setPlainText("\n".join(lines))
        self.status.setText(
            QCoreApplication.translate(
                "Migration",
                "Ready to import {settings} preferences, {presets} icon presets and {extensions} extension bounds.",
            ).format(
                settings=preview.setting_count,
                presets=preview.preset_count,
                extensions=preview.extension_count,
            )
        )
        self.import_button.setEnabled(bool(preview.preferences or preview.projects))

    def _apply(self):
        if self.preview is None:
            return
        try:
            apply_legacy(self.preview, self.settings)
        except Exception as error:
            logger.exception("Failed to import legacy settings")
            error_dialog(self, error)
            return
        self.import_button.setEnabled(False)
        self.status.setText(
            QCoreApplication.translate(
                "Migration",
                "Imported. Defaults apply when reopening original resources; saved projects keep their own edits.",
            )
        )
