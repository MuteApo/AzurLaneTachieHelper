import re
from pathlib import Path
from typing import cast, override

from PySide6.QtCore import QCoreApplication, QSignalBlocker, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from adapters.adb import PACKAGES, AdbClient, PullResult
from adapters.storage import Settings, unique_path
from application.resource_pull import can_open, index_cache, pull_resources, refresh_index, resource_names
from ui.i18n import render_message
from ui.tasks import TaskRunner
from ui.widgets.chrome import WorkbenchDialog, error_dialog
from ui.widgets.controls import SearchComboBox, button, label


class DeviceDialog(WorkbenchDialog):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.metadata: Path | None = None
        self._can_open = False
        self._initialized = False
        self._automatic = False
        self._loading_devices = False
        self._manual_destination = False
        self._devices_online: list[str] = []
        repository = Path(__file__).resolve().parents[3]
        self._download_root = Path(settings.get("pull_directory", "") or repository / "projects")
        configured_index = settings.get("manifest_path", "")
        candidate = Path(configured_index) if configured_index else repository / "dependencies"
        self._manifest_path = (
            candidate
            if candidate.is_file() and (configured_index or settings.get("server", "CN") == "CN")
            else None
        )
        self.setWindowTitle(QCoreApplication.translate("Device", "Download artwork"))
        self.resize(720, 620)
        self.setMinimumWidth(600)
        layout = self.body
        layout.setContentsMargins(28, 28, 28, 24)
        layout.setSpacing(0)
        connection_form = QGridLayout()
        connection_form.setHorizontalSpacing(20)
        connection_form.setVerticalSpacing(8)
        connection_form.setColumnStretch(0, 3)
        connection_form.setColumnStretch(1, 1)
        self.server = QComboBox()
        for key, package in PACKAGES.items():
            self.server.addItem(key, package)
        self.server.setCurrentText(settings.get("server", "CN") or "CN")
        self.package = QLineEdit(settings.get("package_name", "") or self.server.currentData())
        self.serial = SearchComboBox()
        configured_serial = settings.get("serial", "auto") or "auto"
        self.serial.addItem(QCoreApplication.translate("Device", "Choose automatically"), "auto")
        if configured_serial != "auto":
            self.serial.addItem(configured_serial, configured_serial)
            self.serial.setCurrentIndex(1)
        self.serial.setToolTip(
            QCoreApplication.translate(
                "Device", "Select a device, or enter an emulator address such as 127.0.0.1:5555."
            )
        )
        device_row = QHBoxLayout()
        device_row.setSpacing(8)
        device_row.addWidget(self.serial, 1)
        self.refresh_button = button(QCoreApplication.translate("Device", "Refresh"), self._devices)
        self.refresh_button.setObjectName("quiet")
        device_row.addWidget(self.refresh_button)
        connection_form.addWidget(label(QCoreApplication.translate("Device", "Device"), "heading"), 0, 0)
        connection_form.addWidget(label(QCoreApplication.translate("Device", "Server"), "heading"), 0, 1)
        connection_form.addLayout(device_row, 1, 0)
        connection_form.addWidget(self.server, 1, 1)
        layout.addLayout(connection_form)
        layout.addSpacing(24)
        rule = QFrame()
        rule.setObjectName("rule")
        rule.setFixedHeight(1)
        layout.addWidget(rule)
        layout.addSpacing(20)
        self.destination = QLineEdit(str(unique_path(self._download_root / "download")))
        self.destination.textEdited.connect(self._destination_edited)
        self.destination.setPlaceholderText(
            QCoreApplication.translate("Device", "Choose a new folder for this artwork")
        )
        destination_row = QHBoxLayout()
        destination_row.setSpacing(8)
        destination_row.addWidget(self.destination)
        self.destination_button = button(QCoreApplication.translate("Device", "Browse…"), self._destination)
        self.destination_button.setObjectName("secondary")
        destination_row.addWidget(self.destination_button)
        self.name = SearchComboBox()
        name_editor = cast(QLineEdit, self.name.lineEdit())
        name_editor.setPlaceholderText(
            QCoreApplication.translate("Device", "Search resource names, e.g. aidang_2")
        )
        name_row = QHBoxLayout()
        name_row.addWidget(label(QCoreApplication.translate("Device", "Artwork"), "heading"))
        name_row.addStretch()
        self.names_button = button(QCoreApplication.translate("Device", "Refresh list"), self._pull_index)
        self.names_button.setObjectName("quiet")
        self.names_button.setToolTip(QCoreApplication.translate("Device", "Get resource names"))
        name_row.addWidget(self.names_button)
        layout.addLayout(name_row)
        layout.addSpacing(4)
        layout.addWidget(self.name)
        self.name_hint = label(
            QCoreApplication.translate(
                "Device", "Use the game's resource name, not the character's display name."
            ),
            "caption",
        )
        self.name_hint.setWordWrap(True)
        layout.addSpacing(8)
        layout.addWidget(self.name_hint)
        layout.addSpacing(24)
        layout.addWidget(label(QCoreApplication.translate("Device", "Save location"), "heading"))
        layout.addSpacing(8)
        layout.addLayout(destination_row)
        layout.addSpacing(16)
        self.connection_toggle = QToolButton()
        self.connection_toggle.setObjectName("quiet")
        self.connection_toggle.setText(QCoreApplication.translate("Device", "Connection settings"))
        self.connection_toggle.setCheckable(True)
        self.connection_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.connection_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.connection_toggle.toggled.connect(self._toggle_connection_settings)
        layout.addWidget(self.connection_toggle, alignment=Qt.AlignmentFlag.AlignLeft)
        self.connection_settings = QWidget()
        advanced_form = QVBoxLayout(self.connection_settings)
        advanced_form.setContentsMargins(0, 12, 0, 0)
        advanced_form.setSpacing(8)
        advanced_form.addWidget(label(QCoreApplication.translate("Device", "Custom game package"), "heading"))
        advanced_form.addWidget(self.package)
        self.connection_settings.hide()
        layout.addWidget(self.connection_settings)
        self.server.currentIndexChanged.connect(self._server_changed)
        self.serial.activated.connect(self._connection_changed)
        cast(QLineEdit, self.serial.lineEdit()).editingFinished.connect(self._connection_changed)
        self.package.editingFinished.connect(self._connection_changed)
        self._connection_identity = (self.package.text().strip(), self._serial_value())
        self.name.editTextChanged.connect(self._suggest_destination)
        self.form_widgets = [
            self.server,
            self.package,
            self.serial,
            self.name,
            self.destination,
            self.refresh_button,
            self.names_button,
            self.destination_button,
            self.connection_toggle,
        ]
        layout.addStretch()
        layout.addSpacing(20)
        rule = QFrame()
        rule.setObjectName("rule")
        rule.setFixedHeight(1)
        layout.addWidget(rule)
        layout.addSpacing(16)
        self.status = label(QCoreApplication.translate("Device", "Finding online devices…"), "caption")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.hide()
        layout.addWidget(self.progress)
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setMaximumBlockCount(1000)
        self.report.setMaximumHeight(180)
        self.report.hide()
        layout.addWidget(self.report)
        layout.addSpacing(12)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.cancel_button = button(QCoreApplication.translate("Device", "Close"), self.reject)
        self.cancel_button.setObjectName("quiet")
        self.open_button = button(QCoreApplication.translate("Device", "Open project"), self.accept)
        self.open_button.setEnabled(False)
        self.open_button.hide()
        self.pull_button = button(QCoreApplication.translate("Device", "Download"), self._pull, True)
        self.pull_button.setMinimumWidth(100)
        actions.addWidget(self.cancel_button)
        actions.addStretch()
        actions.addWidget(self.open_button)
        actions.addWidget(self.pull_button)
        layout.addLayout(actions)
        self.tasks = TaskRunner(self)
        self.tasks.progress.connect(self._progress)
        self.tasks.failed.connect(self._failed)
        self.tasks.busy_changed.connect(self._busy)
        self.tasks.cancelled.connect(
            lambda: self.status.setText(
                QCoreApplication.translate(
                    "Device", "Pull cancelled; completed files remain in the project folder."
                )
            )
        )

    @override
    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if not self._initialized:
            self._initialized = True
            QTimer.singleShot(0, lambda: self._devices(automatic=True) if self.isVisible() else None)

    def _destination_edited(self):
        self._manual_destination = True

    def _suggest_destination(self, name: str):
        if not self._manual_destination:
            folder = name.strip() if re.fullmatch(r"[\w-]+", name.strip()) else "download"
            self.destination.setText(str(unique_path(self._download_root / folder)))

    def _index_cache(self) -> Path:
        return index_cache(self.settings.path.parent, self.package.text().strip(), self._serial_value())

    def _toggle_connection_settings(self, expanded: bool) -> None:
        self.connection_settings.setVisible(expanded)
        self.connection_toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)

    def _server_changed(self) -> None:
        self.package.setText(self.server.currentData())
        self._connection_changed()

    def _connection_changed(self) -> None:
        if self._serial_value() == "auto" and self._devices_online:
            with QSignalBlocker(self.serial):
                self.serial.setCurrentIndex(self.serial.findData(self._devices_online[0]))
        identity = (self.package.text().strip(), self._serial_value())
        if identity == self._connection_identity:
            return
        self._connection_identity = identity
        self._manifest_path = None
        selected = self.name.currentText()
        with QSignalBlocker(self.name):
            self.name.clear()
            self.name.setCurrentText(selected)
        self._load_names(automatic=True)

    def _show_report(self, text: str) -> None:
        self.report.setPlainText(text)
        self.report.setVisible(bool(text))

    def _client(self) -> AdbClient:
        return AdbClient(
            self.settings.get("adb_path", "adb") or "adb",
            self._serial_value(),
            self.package.text().strip(),
            True,
        )

    def _serial_value(self) -> str:
        if self.serial.currentText() == self.serial.itemText(self.serial.currentIndex()):
            return self.serial.currentData() or "auto"
        return self.serial.currentText().strip() or "auto"

    def _devices(self, *, automatic: bool = False):
        if self.tasks.busy:
            return
        self._automatic = automatic
        self._loading_devices = True
        try:
            client = self._client()
        except ValueError as error:
            self.status.setText(render_message(error))
            return
        self.tasks.start(lambda progress: client.devices(), self._show_devices)

    def _show_devices(self, devices: list[str]):
        self._devices_online = devices
        selected = self._serial_value()
        with QSignalBlocker(self.serial):
            self.serial.clear()
            self.serial.addItem(QCoreApplication.translate("Device", "Choose automatically"), "auto")
            for serial in devices:
                self.serial.addItem(serial, serial)
            if selected == "auto" and devices:
                selected = devices[0]
            selected_index = self.serial.findData(selected)
            if selected_index >= 0:
                self.serial.setCurrentIndex(selected_index)
            else:
                self.serial.setEditText(selected)
        self._connection_identity = (self.package.text().strip(), self._serial_value())
        self.status.setText(
            QCoreApplication.translate("Device", "Found {count} devices.").format(count=len(devices))
            if devices
            else QCoreApplication.translate(
                "Device", "No devices found. Check USB debugging or enter the emulator address."
            )
        )
        self._load_names(automatic=True)

    def _load_names(self, *, automatic: bool = False):
        if self.tasks.busy:
            return
        self._automatic = automatic
        self._loading_devices = False
        cached = self._index_cache()
        path = cached if cached.is_file() else self._manifest_path
        if path is None:
            if not automatic or self._serial_value() in self._devices_online:
                self._pull_index(automatic=automatic)
            return
        self.tasks.start(
            lambda progress: resource_names(path),
            lambda names: self._show_names(path, names),
        )

    def _show_names(self, path: Path, names: list[str]):
        selected = self.name.currentText()
        with QSignalBlocker(self.name):
            self.name.clear()
            self.name.addItems(names)
            self.name.setCurrentIndex(-1)
            self.name.setCurrentText(selected)
        self._manifest_path = path
        self.status.setText(
            QCoreApplication.translate("Device", "{count} artwork resources available").format(
                count=len(names)
            )
        )

    def _destination(self):
        path = QFileDialog.getExistingDirectory(
            self, QCoreApplication.translate("Device", "Select project folder"), self.destination.text()
        )
        if path:
            self._manual_destination = True
            self.destination.setText(path)
            self.status.setText(
                QCoreApplication.translate(
                    "Device", "Get the resource names, or enter a name and choose Download."
                )
            )

    def _pull(self):
        name = self.name.currentText().strip()
        destination_text = self.destination.text().strip()
        if not name or not destination_text:
            self.status.setText(
                QCoreApplication.translate("Device", "Enter a resource name and choose where to save it.")
            )
            return
        destination = Path(destination_text)
        self._automatic = False
        self._loading_devices = False
        try:
            client = self._client()
            self._save_preferences()
        except (ValueError, OSError) as error:
            self.status.setText(render_message(error))
            return
        self.metadata = None
        self._can_open = False

        def completed(value: tuple[PullResult, Path, list[str]]) -> None:
            result, index_file, names = value
            self._show_names(index_file, names)
            self.settings.set("manifest_path", str(index_file.resolve()))
            self._pulled(result)

        self.tasks.start(lambda progress: pull_resources(client, name, destination, progress), completed)

    def _save_preferences(self):
        self.settings.update(
            {
                "server": self.server.currentText(),
                "package_name": self.package.text().strip(),
                "serial": self._serial_value(),
                "pull_directory": str(Path(self.destination.text().strip()).resolve().parent),
            }
        )

    def _pull_index(self, *, automatic: bool = False):
        if self.tasks.busy:
            return
        self._automatic = automatic
        self._loading_devices = False
        try:
            client = self._client()
        except (ValueError, OSError) as error:
            self.status.setText(render_message(error))
            return
        target = self._index_cache()

        def completed(value: tuple[Path, list[str]]) -> None:
            path, names = value
            self._show_names(path, names)

        self.tasks.start(lambda progress: refresh_index(client, target, progress), completed)

    def _pulled(self, result: PullResult):
        self.metadata = result.metadata
        self._can_open = can_open(result)
        self.open_button.setEnabled(self._can_open)
        self.open_button.setVisible(self._can_open)
        self._show_report(
            "\n".join(
                QCoreApplication.translate("Device", "Incomplete: {name}").format(name=name)
                for name in result.failed
            )
        )
        if self._can_open:
            self.status.setText(
                QCoreApplication.translate("Device", "Ready to open. Saved {count} files.").format(
                    count=len(result.files)
                )
                if not result.failed
                else QCoreApplication.translate(
                    "Device", "You can open the artwork. Some expressions or portraits are missing."
                )
            )
        else:
            self.status.setText(
                QCoreApplication.translate(
                    "Device", "Download incomplete. Check the results below and try a new folder."
                )
            )

    def _progress(self, message, current, total):
        self.status.setText(render_message(message))
        self.progress.setRange(0, total)
        self.progress.setValue(current)

    def _failed(self, error, details):
        self.status.setText(render_message(error))
        if self._automatic:
            if self._loading_devices and self._manifest_path and not self.name.count():
                self._load_names(automatic=True)
        else:
            error_dialog(self, error, details)

    def _busy(self, busy):
        self.progress.setVisible(busy)
        self.pull_button.setEnabled(not busy)
        self.open_button.setEnabled(not busy and self._can_open)
        self.open_button.setVisible(self._can_open)
        for widget in self.form_widgets:
            widget.setEnabled(not busy)
        self.cancel_button.setText(
            QCoreApplication.translate("Device", "Cancel")
            if busy
            else QCoreApplication.translate("Device", "Close")
        )

    @override
    def reject(self) -> None:
        if self.tasks.busy:
            self.tasks.cancel()
            self.status.setText(
                QCoreApplication.translate(
                    "Device", "Cancelling; stopping after the current resource finishes…"
                )
            )
        else:
            super().reject()

    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        if self.tasks.busy:
            self.reject()
            event.ignore()
        else:
            event.accept()
