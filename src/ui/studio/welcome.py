from pathlib import Path

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.controls import button, label


class WelcomePage(QWidget):
    folder_requested = Signal()
    file_requested = Signal()
    device_requested = Signal()
    project_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        welcome_outer = QVBoxLayout(self)
        welcome_outer.setContentsMargins(40, 28, 40, 28)
        welcome_card = QWidget()
        welcome_card.setMaximumWidth(820)
        welcome_outer.addWidget(welcome_card, 1, Qt.AlignmentFlag.AlignHCenter)
        welcome = QVBoxLayout(welcome_card)
        welcome.setContentsMargins(0, 0, 0, 0)
        welcome.addStretch(2)
        welcome.addWidget(
            label(QCoreApplication.translate("Window", "Start with your artwork resources"), "emptyTitle")
        )
        welcome.addSpacing(28)
        row = QHBoxLayout()
        self.welcome_folder = button(
            QCoreApplication.translate(
                "Window", "Open resource folder\nFind artwork inside an existing folder"
            ),
            lambda: self.folder_requested.emit(),
            True,
        )
        self.welcome_device = button(
            QCoreApplication.translate(
                "Window", "Get from phone or emulator\nCopy the game's downloaded artwork"
            ),
            lambda: self.device_requested.emit(),
        )
        for widget in (self.welcome_folder, self.welcome_device):
            widget.setMinimumHeight(110)
            widget.setProperty("welcomeAction", True)
            row.addWidget(widget, 1)
        welcome.addLayout(row)
        welcome.addSpacing(14)
        self.welcome_file = button(
            QCoreApplication.translate("Window", "Open saved work or a resource file…"),
            lambda: self.file_requested.emit(),
        )
        welcome.addWidget(self.welcome_file, 0, Qt.AlignmentFlag.AlignLeft)
        hint = label(
            QCoreApplication.translate("Window", "You can also drag a resource folder into this window.")
        )
        hint.setWordWrap(True)
        welcome.addWidget(hint)
        self.recent_layout = QVBoxLayout()
        self.recent_layout.setSpacing(8)
        welcome.addSpacing(30)
        welcome.addLayout(self.recent_layout)
        welcome.addStretch(3)
        self.setFocusProxy(self.welcome_folder)

    def set_recent(self, paths: list[str]) -> None:
        while item := self.recent_layout.takeAt(0):
            if widget := item.widget():
                widget.deleteLater()
        for path in paths[:3]:
            item = button(
                f"↗   {Path(path).name}", lambda checked=False, p=path: self.project_requested.emit(Path(p))
            )
            item.setToolTip(path)
            item.setObjectName("recentItem")
            self.recent_layout.addWidget(item)
