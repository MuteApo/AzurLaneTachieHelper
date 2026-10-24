from pathlib import Path

from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtGui import (
    QDesktopServices,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
)

from ui.widgets.chrome import WorkbenchDialog
from ui.widgets.controls import button


class LogsDialog(WorkbenchDialog):
    def __init__(self, log_path: Path | None, parent=None):
        super().__init__(parent)
        self.log_path = log_path
        self.setWindowTitle(QCoreApplication.translate("Window", "Application logs"))
        self.resize(900, 560)
        layout = self.body
        search = QLineEdit()
        search.setPlaceholderText(
            QCoreApplication.translate("Window", "Filter by ERROR, resource name or a keyword…")
        )
        search.setClearButtonEnabled(True)
        layout.addWidget(search)
        editor = QPlainTextEdit()
        editor.setReadOnly(True)
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        lines: list[str] = []

        def filtered():
            query = search.text().casefold()
            editor.setPlainText("\n".join(line for line in lines if query in line.casefold()))
            bar = editor.verticalScrollBar()
            bar.setValue(bar.maximum())

        search.textChanged.connect(filtered)

        def refresh():
            nonlocal lines
            if self.log_path and self.log_path.exists():
                # Tail without decoding a potentially large rotated log in full.
                with self.log_path.open("rb") as stream:
                    stream.seek(0, 2)
                    stream.seek(max(0, stream.tell() - 200_000))
                    lines = stream.read().decode("utf-8", errors="replace").splitlines()
            else:
                lines = [
                    QCoreApplication.translate("Window", "No file logs have been written in this session.")
                ]
            filtered()

        layout.addWidget(editor)
        row = QHBoxLayout()
        row.addWidget(button(QCoreApplication.translate("Window", "Refresh"), refresh))
        log_path = self.log_path
        if log_path:
            row.addWidget(
                button(
                    QCoreApplication.translate("Window", "Open log folder"),
                    lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_path.parent))),
                )
            )
        row.addStretch()
        row.addWidget(button(QCoreApplication.translate("Window", "Close"), self.accept))
        layout.addLayout(row)
        refresh()
