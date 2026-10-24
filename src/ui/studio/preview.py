from PIL import Image
from PySide6.QtCore import QCoreApplication, QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from application.session import Session
from application.thumbnails import ThumbnailCache
from domain.imaging import replacement_bounds
from domain.messages import Progress
from domain.model import FaceMode, Kind
from ui.studio.assets import (
    THUMBNAIL_PIXELS,
    image_name,
)
from ui.tasks import TaskRunner
from ui.widgets.canvas import Canvas
from ui.widgets.controls import SegmentedChoice, button, label, with_icon


class PreviewPanel(QWidget):
    changed = Signal()
    files_dropped = Signal(object)
    thumbnails_ready = Signal(object)

    def __init__(self, tasks: TaskRunner, parent=None):
        super().__init__(parent)
        self.tasks = tasks
        self._preview_generation = 0
        self._preview_revision: int | None = None
        self._thumbnails = ThumbnailCache(THUMBNAIL_PIXELS)
        self._thumbnail_revision: int | None = None
        self.setObjectName("viewport")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.preview_tools = QWidget()
        toolbar = QHBoxLayout(self.preview_tools)
        toolbar.setContentsMargins(22, 18, 22, 14)
        toolbar.setSpacing(8)
        self.preview_title = label(QCoreApplication.translate("Window", "Preview"), "heading")
        self.preview_title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        caption = QVBoxLayout()
        caption.setSpacing(4)
        caption.addWidget(self.preview_title)
        self.dimensions = label(QCoreApplication.translate("Window", "Ready"))
        caption.addWidget(self.dimensions)
        toolbar.addLayout(caption, 1)
        toolbar.addStretch()
        self.preview_mode = SegmentedChoice(
            [
                (QCoreApplication.translate("Window", "Selected image only"), False),
                (QCoreApplication.translate("Window", "Combined artwork"), True),
            ]
        )
        self.preview_mode.setToolTip(
            QCoreApplication.translate(
                "Window", "Show the artwork together, or just the image selected on the left."
            )
        )
        self.checker = QCheckBox(QCoreApplication.translate("Window", "Transparency grid"))
        self.checker.setChecked(True)
        self.preview_mode.currentIndexChanged.connect(lambda: self.changed.emit())
        self.checker.toggled.connect(lambda value: self.canvas.set_checker(value))
        toolbar.addWidget(self.checker)
        toolbar.addSpacing(8)
        toolbar.addWidget(self.preview_mode)
        layout.addWidget(self.preview_tools)
        self.canvas = Canvas()
        self.setFocusProxy(self.canvas)
        self.canvas.drop_hint = QCoreApplication.translate("Window", "Drop images to choose replacements")
        self.canvas.files_dropped.connect(self.files_dropped.emit)
        self.canvas.set_checker(True)
        layout.addWidget(self.canvas, 1)
        self.preview_footer = QWidget()
        footer = QHBoxLayout(self.preview_footer)
        footer.setContentsMargins(16, 10, 16, 20)
        footer.addStretch()
        zoom_bar = QWidget()
        zoom_bar.setObjectName("zoomBar")
        zoom_row = QHBoxLayout(zoom_bar)
        zoom_row.setContentsMargins(4, 3, 4, 3)
        zoom_row.setSpacing(2)
        minus = with_icon(button("", lambda: self.canvas.zoom_by(1 / 1.15)), "minus")
        plus = with_icon(button("", lambda: self.canvas.zoom_by(1.15)), "plus")
        for widget, title in (
            (minus, QCoreApplication.translate("Window", "Zoom out")),
            (plus, QCoreApplication.translate("Window", "Zoom in")),
        ):
            widget.setToolTip(title)
            widget.setAccessibleName(title)
        zoom_row.addWidget(minus)
        self.zoom = label("—")
        self.zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom.setMinimumWidth(44)
        self.canvas.zoom_changed.connect(lambda factor: self.zoom.setText(f"{factor:.0%}"))
        zoom_row.addWidget(self.zoom)
        zoom_row.addWidget(plus)
        zoom_row.addWidget(button(QCoreApplication.translate("Window", "Fit"), self.canvas.fit))
        actual = button("1:1", self.canvas.actual_size)
        actual.setToolTip(QCoreApplication.translate("Window", "Actual size (100%)"))
        zoom_row.addWidget(actual)
        footer.addWidget(zoom_bar)
        footer.addStretch()
        zoom_bar.setToolTip(QCoreApplication.translate("Window", "Scroll to zoom · Drag to pan"))
        layout.addWidget(self.preview_footer)

    def request(
        self,
        session: Session,
        key: str | None,
        *,
        original: bool = False,
        initial: tuple[Image.Image, dict[str, Image.Image]] | None = None,
    ) -> None:
        if self.tasks.busy:
            return
        self._preview_generation += 1
        generation = self._preview_generation
        if self._preview_revision != session.revision:
            self.canvas.clear_previews()
            self._preview_revision = session.revision
        original = bool(session.project.modified) and original
        composite = self.preview_mode.currentData()
        asset = session.project.asset(key) if key else None
        composite = composite and (asset is None or asset.kind != Kind.ICON)
        actual_size = asset is not None and (
            asset.kind == Kind.ICON
            or (
                asset.kind == Kind.FACE
                and not composite
                and (original or not asset.modified or session.project.options.face_mode == FaceMode.OFF)
            )
        )
        # Selecting another painting does not change the combined image; expressions do.
        render_key = key if not composite or (asset and asset.kind == Kind.FACE) else None
        cache_key = render_key, original, composite
        self.preview_mode.setVisible(asset is None or asset.kind != Kind.ICON)
        self.preview_title.setText(
            QCoreApplication.translate("Window", "Artwork preview")
            if composite
            else image_name(asset)
            if asset
            else QCoreApplication.translate("Window", "Preview")
        )
        self.preview_title.setToolTip(self.preview_title.text())

        def describe() -> None:
            variant = (
                QCoreApplication.translate("Window", "Before edits")
                if original
                else QCoreApplication.translate("Window", "With edits")
                if session.project.modified
                else QCoreApplication.translate("Window", "Preview")
            )
            rendered = self.canvas.item.pixmap()
            self.dimensions.setText(f"{rendered.width():,} × {rendered.height():,} px  ·  {variant}")
            boundary = None
            if composite and asset and not original and session.project.options.face_mode == FaceMode.CUSTOM:
                boundary = replacement_bounds(session.project, asset)
            self.canvas.set_boundary(boundary)

        if self.canvas.show_cached(cache_key, actual_size=actual_size):
            describe()
            return

        def shown(result: tuple[Image.Image, dict[str, Image.Image] | None]) -> None:
            if generation != self._preview_generation:
                return
            image, thumbnails = result
            self.canvas.set_image(image, cache_key, actual_size=actual_size)
            if thumbnails is not None:
                self.thumbnails_ready.emit(thumbnails)
                self._thumbnail_revision = session.revision
            describe()

        if initial is not None:
            shown(initial)
            return

        def prepare(progress: Progress):
            progress(QCoreApplication.translate("Window", "Generating preview…"), 0, 0)
            image = session.preview(render_key, original=original, composite=composite)
            thumbnails = (
                self._thumbnails.prepare(session.project)
                if self._thumbnail_revision != session.revision
                else None
            )
            return image, thumbnails

        self.tasks.start(prepare, shown)

    def reset(self, thumbnails: ThumbnailCache | None = None) -> None:
        self._preview_generation += 1
        self._preview_revision = None
        self._thumbnail_revision = None
        self._thumbnails = thumbnails if thumbnails is not None else ThumbnailCache(THUMBNAIL_PIXELS)
        self.canvas.clear()
        with QSignalBlocker(self.preview_mode):
            self.preview_mode.setCurrentData(False)

    def show_composite(self) -> None:
        """Select the combined view; the caller requests pixels after the edit."""
        with QSignalBlocker(self.preview_mode):
            self.preview_mode.setCurrentData(True)

    def fit(self) -> None:
        self.canvas.fit()

    def actual_size(self) -> None:
        self.canvas.actual_size()

    def set_available(self, opened: bool, idle: bool) -> None:
        self.preview_mode.setEnabled(opened and idle)
        self.canvas.drop_enabled = idle
        if not idle:
            self.set_drop_active(False)

    def set_drop_active(self, active: bool) -> None:
        self.canvas.set_drop_active(active)
