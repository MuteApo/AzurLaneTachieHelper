import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast, override

from PIL import Image
from PySide6.QtCore import QT_TRANSLATE_NOOP, QCoreApplication, Qt, QTimer, QUrl
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QColor,
    QDesktopServices,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDropEvent,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from application.session import Session
from application.thumbnails import ThumbnailCache
from domain.messages import Progress
from domain.model import FaceMode, Kind
from ui.dialogs.alignment import AlignmentDialog
from ui.dialogs.export import ExportDialog
from ui.dialogs.image_import import ImportDialog
from ui.dialogs.logs import LogsDialog
from ui.dialogs.portrait import CropDialog
from ui.dialogs.preferences import PreferencesDialog
from ui.i18n import render_message
from ui.studio.assets import (
    THUMBNAIL_PIXELS,
)
from ui.studio.inspector import InspectorPanel
from ui.studio.preview import PreviewPanel
from ui.studio.sidebar import AssetSidebar
from ui.studio.welcome import WelcomePage
from ui.tasks import TaskRunner
from ui.theme import COLORS, apply_theme
from ui.widgets.chrome import WindowHeader, WorkbenchMessageBox, error_dialog
from ui.widgets.controls import NoticeOverlay, PopupButton, button, icon, label, with_icon

logger = logging.getLogger(__name__)
IMAGE_FILTER = str(
    QT_TRANSLATE_NOOP("Window", "Images (*.png *.webp *.jpg *.jpeg *.tif *.tiff *.bmp);;All files (*)")
)


@dataclass
class _LoadedProject:
    session: Session
    selected_key: str | None
    image: Image.Image
    thumbnails: dict[str, Image.Image]
    thumbnail_cache: ThumbnailCache


class MainWindow(QMainWindow):
    """The view owns selection and dialogs; Session owns every persistent edit."""

    def __init__(self, settings, log_path: Path | None = None):
        super().__init__()
        self.settings, self.log_path = settings, log_path
        self.session: Session | None = None
        self.selected_key: str | None = None
        self._opening: Path | None = None
        self._relocations: dict[str, Path] = {}
        self._after_save = None
        self.last_output: Path | None = None
        self._theme_override: Qt.ColorScheme | None = None
        self.resize(1440, 920)
        self.setMinimumSize(1120, 700)
        self.setWindowTitle(QCoreApplication.translate("Window", "Tachie Studio · Artwork Workbench"))
        self.setAcceptDrops(True)
        self.tasks = TaskRunner(self)
        self.tasks.busy_changed.connect(self._busy)
        self.tasks.progress.connect(self._progress)
        self.tasks.failed.connect(self._failed)
        self.tasks.cancelled.connect(self._cancelled)
        self._build_actions()
        self._build_layout()
        self._update_state()
        self._apply_theme(QApplication.styleHints().colorScheme())
        QApplication.styleHints().colorSchemeChanged.connect(self._apply_theme)

    def _apply_theme(self, scheme: Qt.ColorScheme):
        scheme = self._theme_override or scheme
        apply_theme(cast(QApplication, QApplication.instance()), scheme)
        variant = 0 if scheme == Qt.ColorScheme.Dark else 1
        disabled_color = QColor(COLORS["disabled_text"][variant])
        for widget in self.findChildren(QAbstractButton):
            name = widget.property("glyph")
            if not name:
                continue
            role = "primary_text" if widget is self.export_button else "text"
            widget.setIcon(icon(name, QColor(COLORS[role][variant]), disabled_color))
        self.sidebar.refresh_palette()

    def _set_theme(self, scheme: Qt.ColorScheme | None):
        self._theme_override = scheme
        QApplication.styleHints().setColorScheme(scheme or Qt.ColorScheme.Unknown)
        self._apply_theme(QApplication.styleHints().colorScheme())

    def _action(self, title, shortcut, callback):
        action = QAction(title, self)
        if shortcut:
            action.setShortcut(shortcut)
        action.triggered.connect(callback)
        self.addAction(action)
        return action

    def _build_actions(self):
        self.open_action = self._action(
            QCoreApplication.translate("Window", "Open resources…"),
            QKeySequence.StandardKey.Open,
            self.choose_open,
        )
        self.close_project_action = self._action(
            QCoreApplication.translate("Window", "Close project"), "Ctrl+W", self.close_project
        )
        self.save_action = self._action(
            QCoreApplication.translate("Window", "Save work"), QKeySequence.StandardKey.Save, self.save
        )
        self.save_as_action = self._action(
            QCoreApplication.translate("Window", "Save work as…"),
            QKeySequence.StandardKey.SaveAs,
            self.save_as,
        )
        self.undo_action = self._action(
            QCoreApplication.translate("Window", "Undo"), QKeySequence.StandardKey.Undo, self.undo
        )
        self.redo_action = self._action(
            QCoreApplication.translate("Window", "Redo"), QKeySequence.StandardKey.Redo, self.redo
        )
        self.import_action = self._action(
            QCoreApplication.translate("Window", "Replace images…"), "Ctrl+I", self.import_images
        )
        self.psd_action = self._action(
            QCoreApplication.translate("Window", "Export layered image (PSD)…"),
            "Ctrl+Shift+E",
            self.export_psd,
        )
        self.export_action = self._action(
            QCoreApplication.translate("Window", "Export game replacement files…"),
            "Ctrl+E",
            self.export_unity,
        )
        self.crop_action = self._action(
            QCoreApplication.translate("Window", "Create portraits…"), "Ctrl+K", self.crop_icons
        )
        self.device_action = self._action(
            QCoreApplication.translate("Window", "Get from phone or emulator…"), None, self.pull_resources
        )
        self.preferences_action = self._action(
            QCoreApplication.translate("Window", "Preferences…"), None, self.preferences
        )
        self.migration_action = self._action(
            QCoreApplication.translate("Window", "Import legacy settings…"), None, self.import_legacy
        )
        self.app_menu = QMenu(self)
        file_menu = self.app_menu.addMenu(QCoreApplication.translate("Window", "File"))
        file_menu.addAction(self.open_action)
        self.recent_menu = file_menu.addMenu(QCoreApplication.translate("Window", "Recent projects"))
        self._recent_menu()
        file_menu.addAction(self.device_action)
        file_menu.addSeparator()
        file_menu.addActions([self.save_action, self.save_as_action])
        file_menu.addSeparator()
        file_menu.addActions([self.psd_action, self.export_action])
        file_menu.addSeparator()
        file_menu.addAction(self.close_project_action)
        file_menu.addAction(self._action(QCoreApplication.translate("Window", "Exit"), "Alt+F4", self.close))
        edit_menu = self.app_menu.addMenu(QCoreApplication.translate("Window", "Edit"))
        edit_menu.addActions([self.undo_action, self.redo_action])
        edit_menu.addSeparator()
        edit_menu.addActions([self.import_action, self.crop_action, self.preferences_action])
        edit_menu.addAction(self.migration_action)
        view_menu = self.app_menu.addMenu(QCoreApplication.translate("Window", "View"))
        view_menu.addAction(
            self._action(
                QCoreApplication.translate("Window", "Fit canvas"),
                "Ctrl+0",
                lambda: self.preview.fit(),
            )
        )
        view_menu.addAction(
            self._action(
                QCoreApplication.translate("Window", "Actual size (100%)"),
                "Ctrl+1",
                lambda: self.preview.actual_size(),
            )
        )
        view_menu.addAction(
            self._action(QCoreApplication.translate("Window", "View logs…"), None, self.show_logs)
        )

    def _build_layout(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.header = WindowHeader(self)
        root.setAttribute(Qt.WidgetAttribute.WA_ContentsMarginsRespectsSafeArea, False)
        row = self.header.row
        self.menu_button = PopupButton(self.app_menu)
        self.menu_button.setText("T")
        self.menu_button.setObjectName("appMenu")
        self.menu_button.setFixedSize(34, 34)
        self.menu_button.setToolTip(QCoreApplication.translate("Window", "Application menu · F10"))
        self.menu_button.setAccessibleName(QCoreApplication.translate("Window", "Application menu"))
        self._action(
            QCoreApplication.translate("Window", "Application menu"), "F10", self.menu_button.show_popup
        )
        row.addWidget(self.menu_button)
        brand = QVBoxLayout()
        brand.setSpacing(2)
        brand.addWidget(label(QCoreApplication.translate("Window", "Artwork Studio"), "brand"))
        row.addLayout(brand)
        row.addSpacing(20)
        self.project_title = label(QCoreApplication.translate("Window", "Open a project to begin"))
        self.project_title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        row.addWidget(self.project_title, 1)
        self.close_project_button = button(
            QCoreApplication.translate("Window", "Close project"), self.close_project
        )
        self.close_project_button.setObjectName("quiet")
        self.close_project_button.setToolTip(
            QCoreApplication.translate("Window", "Close project and return to start · Ctrl+W")
        )
        row.addWidget(self.close_project_button)
        self.undo_button = with_icon(button("", self.undo), "undo")
        self.redo_button = with_icon(button("", self.redo), "redo")
        self.undo_button.setAccessibleName(QCoreApplication.translate("Window", "Undo"))
        self.redo_button.setAccessibleName(QCoreApplication.translate("Window", "Redo"))
        self.undo_button.setObjectName("quiet")
        self.redo_button.setObjectName("quiet")
        self.undo_button.setToolTip(QCoreApplication.translate("Window", "Undo · Ctrl+Z"))
        self.redo_button.setToolTip(QCoreApplication.translate("Window", "Redo · Ctrl+Shift+Z"))
        row.addWidget(self.undo_button)
        row.addWidget(self.redo_button)
        row.addSpacing(10)
        self.saved_badge = label(QCoreApplication.translate("Window", "Local workspace"), "badge")
        row.addWidget(self.saved_badge)
        row.addSpacing(10)
        self.save_button = button(QCoreApplication.translate("Window", "Save work"), self.save)
        self.save_button.setObjectName("quiet")
        self.save_button.setToolTip(
            QCoreApplication.translate("Window", "Keep your edits so you can continue later.")
        )
        theme_menu = QMenu(self)
        self.theme_button = theme_button = with_icon(PopupButton(theme_menu), "theme")
        theme_button.setObjectName("quiet")
        theme_button.setFixedSize(34, 34)
        theme_button.setToolTip(QCoreApplication.translate("Window", "Appearance"))
        theme_button.setAccessibleName(theme_button.toolTip())
        theme_group = QActionGroup(theme_menu)
        for title, scheme in [
            (QCoreApplication.translate("Window", "Follow system"), None),
            (QCoreApplication.translate("Window", "Light"), Qt.ColorScheme.Light),
            (QCoreApplication.translate("Window", "Dark"), Qt.ColorScheme.Dark),
        ]:
            action = theme_menu.addAction(title)
            action.setCheckable(True)
            theme_group.addAction(action)
            action.setChecked(scheme is None)
            action.triggered.connect(lambda checked=False, value=scheme: self._set_theme(value))
        row.addWidget(theme_button)
        self.export_button = with_icon(
            button(QCoreApplication.translate("Window", "Export"), self.export_unity, True), "export"
        )
        self.export_button.setToolTip(QCoreApplication.translate("Window", "Export game replacement files…"))
        for widget in (self.save_button, self.export_button):
            row.addWidget(widget)
        layout.addWidget(self.header)
        self._build_feedback()
        self.completion = QWidget()
        self.completion.setObjectName("notice")
        notice = QHBoxLayout(self.completion)
        notice.setContentsMargins(24, 12, 24, 12)
        self.completion_text = label("", "heading")
        self.completion_text.setWordWrap(True)
        notice.addWidget(self.completion_text, 1)
        notice.addWidget(button(QCoreApplication.translate("Window", "Open folder"), self.open_output))
        dismiss = button("×", self.completion.hide)
        dismiss.setToolTip(QCoreApplication.translate("Window", "Dismiss"))
        notice.addWidget(dismiss)
        self.completion.hide()
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(1)
        workspace = QWidget()
        work = QHBoxLayout(workspace)
        work.setContentsMargins(0, 0, 0, 0)
        work.addWidget(self.splitter)
        self.sidebar = AssetSidebar()
        self.sidebar.open_requested.connect(self.choose_open)
        self.sidebar.selection_changed.connect(self._selected)
        self.preview = PreviewPanel(self.tasks)
        self.preview.changed.connect(self._request_preview)
        self.preview.files_dropped.connect(self._drop_paths)
        self.preview.thumbnails_ready.connect(self.sidebar.set_thumbnails)
        self.inspector = InspectorPanel()
        self.inspector.psd_requested.connect(self.export_psd)
        self.inspector.import_requested.connect(self.import_images)
        self.inspector.portrait_requested.connect(self.crop_icons)
        self.inspector.replace_requested.connect(self.replace_selected)
        self.inspector.reset_requested.connect(self.reset_selected)
        self.inspector.original_changed.connect(self._request_preview)
        self.inspector.options_changed.connect(self._options)
        self.inspector.extensions_changed.connect(self._extensions)
        self.welcome = WelcomePage()
        self.welcome.folder_requested.connect(self.choose_folder)
        self.welcome.file_requested.connect(self.choose_file)
        self.welcome.device_requested.connect(self.pull_resources)
        self.welcome.project_requested.connect(self.open_path)
        self.welcome.set_recent(self.settings.get("recent_projects", []))
        self.stack = QStackedWidget()
        self.stack.addWidget(self.welcome)
        self.stack.addWidget(self.preview)
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.stack)
        self.splitter.addWidget(self.inspector)
        self.splitter.setSizes([260, 914, 264])
        layout.addWidget(workspace, 1)
        self.notices = NoticeOverlay(workspace, [self.feedback, self.completion])

    def _build_feedback(self):
        self.feedback = QWidget()
        self.feedback.setObjectName("notice")
        row = QHBoxLayout(self.feedback)
        row.setContentsMargins(22, 6, 22, 6)
        self.feedback_text = label("")
        self.feedback_text.setWordWrap(True)
        self.feedback_text.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        row.addWidget(self.feedback_text, 1)
        self.progress = QProgressBar()
        self.progress.setFixedWidth(150)
        self.progress.setTextVisible(False)
        self.progress.hide()
        self.cancel_button = button(QCoreApplication.translate("Window", "Cancel task"), self.tasks.cancel)
        self.cancel_button.setObjectName("statusAction")
        self.cancel_button.hide()
        row.addWidget(self.progress)
        row.addWidget(self.cancel_button)
        self.feedback.hide()
        self._feedback_timer = QTimer(self)
        self._feedback_timer.setSingleShot(True)
        self._feedback_timer.timeout.connect(self.feedback.hide)
        self._task_notice_timer = QTimer(self)
        self._task_notice_timer.setSingleShot(True)
        self._task_notice_timer.setInterval(200)
        self._task_notice_timer.timeout.connect(self.feedback.show)

    def _show_message(self, text: str, timeout: int = 6000):
        self.feedback_text.setText(text)
        self.feedback_text.setToolTip(text)
        self.feedback.show()
        if not self.tasks.busy:
            self._feedback_timer.start(timeout)

    def _recent_menu(self):
        self.recent_menu.clear()
        for path in self.settings.get("recent_projects", [])[:8]:
            action = self.recent_menu.addAction(Path(path).name)
            action.setToolTip(path)
            action.triggered.connect(lambda checked=False, p=path: self.open_path(Path(p)))
        self.recent_menu.setEnabled(bool(self.recent_menu.actions()))

    def _remember(self, path):
        value = str(path.resolve())
        recent = [value] + [p for p in self.settings.get("recent_projects", []) if p != value]
        self.settings.set("recent_projects", recent[:8])
        self._recent_menu()

    def choose_open(self):
        from ui.dialogs.resource_open import choose_resource

        path = choose_resource(self)
        if path:
            self.open_path(path)

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, QCoreApplication.translate("Window", "Choose the folder containing your artwork resources")
        )
        if path:
            self.open_path(Path(path))

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            QCoreApplication.translate("Window", "Open saved work or a resource file"),
            "",
            QCoreApplication.translate(
                "Window", "Projects and assets (*.tachie.json *.json *);;All files (*)"
            ),
        )
        if path:
            self.open_path(Path(path))

    def _resolve_folder(self, folder: Path) -> Path | None:
        from ui.dialogs.resource_open import choose_resource

        return choose_resource(self, folder)

    def open_path(self, path: Path):
        if self.tasks.busy:
            return
        if path.is_dir():
            resolved = self._resolve_folder(path)
            if resolved is None:
                return
            path = resolved
        if not self._confirm_discard(lambda: self.open_path(path)):
            return
        self._opening = path
        self._relocations = {}
        self._load_project()

    def _load_project(self):
        path = self._opening
        if path is None:
            return
        manifest_text = self.settings.get("manifest_path", "")
        manifest = Path(manifest_text) if manifest_text else None
        relocations = dict(self._relocations)
        defaults = self.settings.data.model_copy(deep=True)

        def load(progress: Progress) -> _LoadedProject:
            progress(QCoreApplication.translate("Window", "Reading project…"), 0, 0)
            session = Session.open(
                path, manifest=manifest, progress=progress, relocations=relocations, defaults=defaults
            )
            try:
                progress(QCoreApplication.translate("Window", "Generating preview…"), 0, 0)
                project = session.project
                key = (
                    project.preferred().key
                    if project.paintings
                    else next(
                        (
                            asset.key
                            for kind in (Kind.FACE, Kind.ICON)
                            for asset in project.assets
                            if asset.kind == kind
                        ),
                        None,
                    )
                )
                image = session.preview(key)
                cache = ThumbnailCache(THUMBNAIL_PIXELS)
                thumbnails = cache.prepare(project)
                # Observe cancellation before handing the new session to the UI.
                progress(QCoreApplication.translate("Window", "Generating preview…"), 1, 1)
                return _LoadedProject(session, key, image, thumbnails, cache)
            except Exception:
                session.close()
                raise

        self.tasks.start(load, lambda result: self._opened(result.session, initial=result))

    def _opened(self, session: Session, *, initial: _LoadedProject | None = None) -> None:
        if self.session is not None:
            self.session.close()
        self.session = session
        self.preview.reset(initial.thumbnail_cache if initial else None)
        self.sidebar.clear()
        self.inspector.show_edits()
        self.completion.hide()
        self.selected_key = (
            initial.selected_key
            if initial
            else session.project.preferred().key
            if session.project.paintings
            else None
        )
        path = self._opening
        self._opening = None
        if path:
            self._remember(path)
        self.stack.setCurrentWidget(self.preview)
        self._refresh(initial=initial)
        self.preview.setFocus()

    def close_project(self):
        if self.session is None or self.tasks.busy:
            return
        if not self._confirm_discard(self.close_project):
            return
        session, self.session = self.session, None
        self.selected_key = None
        session.close()
        self.preview.reset()
        self.sidebar.clear()
        self._opening = None
        self._relocations.clear()
        self._after_save = None
        self.last_output = None
        self.completion.hide()
        self._feedback_timer.stop()
        self._task_notice_timer.stop()
        self.feedback.hide()
        self.project_title.clear()
        self.project_title.setToolTip("")
        self.setWindowTitle(QCoreApplication.translate("Window", "Tachie Studio · Artwork Workbench"))
        self.welcome.set_recent(self.settings.get("recent_projects", []))
        self.stack.setCurrentWidget(self.welcome)
        self._update_state()
        self.welcome.setFocus()

    def _refresh(self, *, initial: _LoadedProject | None = None):
        if self.session is None:
            return
        self.selected_key = self.sidebar.set_project(self.session.project, self.selected_key)
        self._update_inspector()
        self._update_state()
        self._request_preview(initial=initial)

    def _selected(self, key: str) -> None:
        self.selected_key = key
        self._update_inspector()
        self._update_state()
        self._request_preview()

    def _update_inspector(self):
        if self.session:
            self.inspector.set_asset(self.session.project, self.selected_key)

    def _update_state(self):
        session = self.session
        idle = not self.tasks.busy
        opened = session is not None
        self.preview.set_available(opened, idle)
        for widget in (
            self.sidebar,
            self.inspector,
            self.project_title,
            self.close_project_button,
            self.undo_button,
            self.redo_button,
            self.saved_badge,
            self.save_button,
            self.export_button,
        ):
            widget.setVisible(opened)
        self.welcome.setEnabled(idle)
        for action in (
            self.save_action,
            self.save_as_action,
            self.close_project_action,
            self.import_action,
            self.psd_action,
            self.crop_action,
        ):
            action.setEnabled(opened and idle)
        self.export_action.setEnabled(opened and idle and bool(session.project.modified))
        self.open_action.setEnabled(idle)
        self.device_action.setEnabled(idle)
        self.recent_menu.setEnabled(idle and bool(self.recent_menu.actions()))
        self.undo_action.setEnabled(opened and idle and session.can_undo)
        self.redo_action.setEnabled(opened and idle and session.can_redo)
        self.undo_button.setEnabled(self.undo_action.isEnabled())
        self.redo_button.setEnabled(self.redo_action.isEnabled())
        self.undo_action.setText(
            QCoreApplication.translate("Window", "Undo {0}").format(render_message(session.undo_label))
            if opened and session.can_undo
            else QCoreApplication.translate("Window", "Undo")
        )
        self.redo_action.setText(
            QCoreApplication.translate("Window", "Redo {0}").format(render_message(session.redo_label))
            if opened and session.can_redo
            else QCoreApplication.translate("Window", "Redo")
        )
        self.sidebar.set_available(idle)
        self.save_button.setEnabled(opened and idle)
        self.close_project_button.setEnabled(self.close_project_action.isEnabled())
        self.export_button.setEnabled(self.export_action.isEnabled())
        self.inspector.set_available(session.project if session else None, self.selected_key, idle)
        if opened:
            self.project_title.setText(session.project.name)
            self.project_title.setToolTip(session.project.name)
            self.saved_badge.setText(
                QCoreApplication.translate("Window", "Unsaved edits")
                if session.dirty
                else QCoreApplication.translate("Window", "Work saved")
                if session.path
                else QCoreApplication.translate("Window", "Original assets")
            )
            self.setWindowTitle(f"{'● ' if session.dirty else ''}{session.project.name} · Tachie Studio")
            self.crop_action.setEnabled(idle and session.project.face is not None)

    def _request_preview(self, *args, initial: _LoadedProject | None = None):
        if self.session:
            self.preview.request(
                self.session,
                self.selected_key,
                original=self.inspector.showing_original,
                initial=(initial.image, initial.thumbnails) if initial else None,
            )

    def _edit(self, function: Callable[[], object], message: str, *, fit_preview: bool = False) -> None:
        self.completion.hide()

        def completed(result: object) -> None:
            if fit_preview and self.session and self.selected_key:
                if self.session.project.asset(self.selected_key).kind != Kind.ICON:
                    self.preview.fit()
            self._refresh()
            self._show_message(message, 8000)

        self.tasks.start(lambda progress: function(), completed)

    def undo(self):
        if self.session and self.session.can_undo:
            self._edit(self.session.undo, QCoreApplication.translate("Window", "Undone"))

    def redo(self):
        if self.session and self.session.can_redo:
            self._edit(self.session.redo, QCoreApplication.translate("Window", "Redone"))

    def _options(self, options: dict) -> None:
        session = self.session
        if session is not None and not self.tasks.busy:
            self._edit(
                lambda: session.set_options(**options),
                QCoreApplication.translate("Window", "Processing options updated"),
            )

    def _extensions(self, value: tuple[int, int, int, int]):
        session = self.session
        if session is None or self.selected_key is None or self.tasks.busy:
            return
        asset = session.project.asset(self.selected_key)
        key = "paintingface" if asset.kind == Kind.FACE else asset.key
        if value == session.project.options.extensions.get(key, (0, 0, 0, 0)):
            return
        extensions = {**session.project.options.extensions, key: value}
        # Bounds need the surrounding canvas as a stable visual reference.
        self.preview.show_composite()
        self.inspector.show_edits()
        self._edit(
            lambda: session.set_options(extensions=extensions),
            QCoreApplication.translate("Window", "Bounds updated"),
        )

    def replace_selected(self):
        session = self.session
        if not self.selected_key or not session:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            QCoreApplication.translate("Window", "Choose a replacement image"),
            "",
            QCoreApplication.translate("Window", IMAGE_FILTER),
        )
        if path:
            mapping = {self.selected_key: Path(path)}
            self._import_mapping(
                mapping,
                QCoreApplication.translate("Window", "Image replaced. Choose Before edits to compare."),
            )

    def import_images(self, paths=None):
        session = self.session
        if not session or self.tasks.busy:
            return
        if not isinstance(paths, list):
            filenames, _ = QFileDialog.getOpenFileNames(
                self,
                QCoreApplication.translate("Window", "Choose images (multiple selection supported)"),
                "",
                QCoreApplication.translate("Window", IMAGE_FILTER),
            )
            paths = [Path(p) for p in filenames]
        if not paths:
            return
        dialog = ImportDialog(self.session, paths, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            mapping = dialog.mapping()
            self._import_mapping(
                mapping,
                QCoreApplication.translate("Window", "Imported {0} images").format(len(mapping)),
            )

    def _import_mapping(self, mapping: dict[str, Path], message: str):
        session = self.session
        if session is None or self.tasks.busy:
            return

        def prepared(items):
            mismatched = [item for item in items if item.size != item.canvas_size]
            alignments = {}
            if mismatched:
                dialog = AlignmentDialog(mismatched, self)
                if dialog.exec() != QDialog.DialogCode.Accepted:
                    return
                alignments = dialog.alignments
            self._edit(
                lambda: session.import_prepared(items, alignments),
                message,
                fit_preview=session.project.options.face_mode != FaceMode.OFF,
            )

        self.tasks.start(lambda progress: session.prepare_imports(mapping), prepared)

    def reset_selected(self):
        session = self.session
        if session and self.selected_key:
            key = self.selected_key
            self._edit(
                lambda: session.reset(key), QCoreApplication.translate("Window", "Selected layer reset")
            )

    def save(self, checked=False):
        if not self.session or self.tasks.busy:
            return
        if self.session.path is None:
            self.save_as()
        else:
            self._save_to(self.session, self.session.path)

    def save_as(self):
        if not self.session:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            QCoreApplication.translate("Window", "Save your work to continue later"),
            f"{self.session.project.name}.tachie.json",
            QCoreApplication.translate("Window", "Tachie project (*.tachie.json)"),
        )
        if path:
            self._save_to(self.session, Path(path))
        else:
            self._after_save = None

    def _save_to(self, session: Session, path: Path):
        def saved(result: Path) -> None:
            self._remember(path)
            self._update_state()
            self._show_message(
                QCoreApplication.translate("Window", "Work saved: {0}. You can continue later.").format(
                    path.name
                ),
                10000,
            )
            continuation = self._after_save
            self._after_save = None
            if continuation:
                continuation()

        self.tasks.start(lambda progress: session.save(path), saved)

    def _confirm_discard(self, continuation=None) -> bool:
        if self.session is None or not self.session.dirty:
            return True
        box = WorkbenchMessageBox(self)
        box.setWindowTitle(QCoreApplication.translate("Window", "Save your edits?"))
        box.setText(QCoreApplication.translate("Window", "This project has unsaved edits."))
        box.setInformativeText(
            QCoreApplication.translate("Window", "Save your work if you want to continue editing later.")
        )
        box.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        box.button(QMessageBox.StandardButton.Save).setText(QCoreApplication.translate("Window", "Save work"))
        box.button(QMessageBox.StandardButton.Discard).setText(
            QCoreApplication.translate("Window", "Discard edits")
        )
        box.button(QMessageBox.StandardButton.Cancel).setText(QCoreApplication.translate("Window", "Cancel"))
        answer = box.exec()
        if answer == QMessageBox.StandardButton.Save:
            self._after_save = continuation
            self.save()
            return False
        return answer == QMessageBox.StandardButton.Discard

    def export_psd(self):
        session = self.session
        if not session or self.tasks.busy:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            QCoreApplication.translate("Window", "Save layered image (PSD)"),
            f"{session.project.name}.psd",
            "PSD (*.psd)",
        )
        if path:
            self.tasks.start(
                lambda progress: session.export_psd(Path(path), progress=progress),
                lambda result: self._exported(
                    Path(path),
                    QCoreApplication.translate(
                        "Window", "PSD saved. Open it in your painting app to edit the layers."
                    ),
                ),
            )

    def export_unity(self):
        session = self.session
        if not session or self.tasks.busy:
            return
        dialog = ExportDialog(session.project, self.settings.get("output_directory", ""), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        destination = Path(dialog.directory.text().strip()).resolve()
        self.settings.set("output_directory", str(destination))
        self.tasks.start(
            lambda progress: session.export_unity(destination, progress=progress),
            lambda result: self._exported(
                self._output_root(result, destination),
                QCoreApplication.translate("Window", "Saved {0} game replacement files.").format(len(result)),
            ),
        )

    @staticmethod
    def _output_root(paths: list[Path], destination: Path) -> Path:
        return destination / paths[0].relative_to(destination).parts[0] if paths else destination

    def _exported(self, path: Path, message: str):
        self.last_output = path if path.is_dir() else path.parent
        self.completion_text.setText(message)
        self.completion_text.setToolTip(str(path))
        self.completion.show()
        self._update_state()

    def open_output(self):
        if self.last_output:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_output)))

    def crop_icons(self):
        session = self.session
        if not session or self.tasks.busy:
            return
        reference, _ = QFileDialog.getOpenFileName(
            self,
            QCoreApplication.translate("Window", "Choose full artwork for portrait cropping"),
            "",
            QCoreApplication.translate("Window", IMAGE_FILTER),
        )
        if not reference:
            return
        path = Path(reference)
        self.tasks.start(
            lambda progress: session.prepare_icon(path), lambda prepared: self._crop(session, path, prepared)
        )

    def _crop(self, session: Session, reference: Path, prepared: tuple[Image.Image, tuple[float, float]]):
        references = {a.name: a.original for a in session.project.assets if a.kind == Kind.ICON}
        source, center = prepared
        dialog = CropDialog(source, center, session.presets, references, self)
        while True:
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            output = None
            if not dialog.save_files.isChecked():
                break
            directory = QFileDialog.getExistingDirectory(
                self, QCoreApplication.translate("Window", "Choose a portrait output folder")
            )
            if directory:
                output = Path(directory)
                break
        presets = dict(dialog.presets)

        def crop(progress: Progress) -> list[Path]:
            return session.clip_icons(reference, presets, output)

        def completed(paths: list[Path]) -> None:
            self._refresh()
            if paths:
                self._exported(
                    paths[0].parent,
                    QCoreApplication.translate(
                        "Window", "Saved {0} portrait PNGs and applied them to this artwork."
                    ).format(len(paths)),
                )
            else:
                self._show_message(
                    QCoreApplication.translate("Window", "Portraits applied to your edits."), 8000
                )

        self.completion.hide()
        self.tasks.start(crop, completed)

    def pull_resources(self):
        if self.tasks.busy:
            return
        from ui.dialogs.resource_pull import DeviceDialog

        dialog = DeviceDialog(self.settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.metadata:
            self.open_path(dialog.metadata)

    def preferences(self):
        PreferencesDialog(self.settings, self).exec()

    def import_legacy(self):
        from ui.dialogs.migration import MigrationDialog

        MigrationDialog(self.settings, self).exec()

    def show_logs(self):
        LogsDialog(self.log_path, self).exec()

    def _busy(self, busy):
        self._feedback_timer.stop()
        self._task_notice_timer.stop()
        self.progress.setVisible(busy)
        self.cancel_button.setVisible(busy)
        if busy:
            self.progress.setRange(0, 0)
            self._task_notice_timer.start()
        else:
            self.feedback.hide()
        self._update_state()

    def _progress(self, message, current, total):
        text = render_message(message)
        self.feedback_text.setText(text)
        self.feedback_text.setToolTip(text)
        self.progress.setRange(0, total)
        self.progress.setValue(current)

    def _failed(self, error, details):
        self._after_save = None
        self._update_inspector()
        if self._opening and hasattr(error, "path") and hasattr(error, "role"):
            path, _ = QFileDialog.getOpenFileName(
                self,
                QCoreApplication.translate("Window", "Locate missing {0}: {1}").format(
                    render_message(error.role), error.path.name
                ),
                "",
                QCoreApplication.translate("Window", "All files (*)"),
            )
            if path:
                self._relocations[str(error.path)] = Path(path)
                QTimer.singleShot(0, self._load_project)
                return
        self._opening = None
        error_dialog(self, error, details)

    def _cancelled(self):
        self._opening = None
        self._relocations.clear()
        self._show_message(QCoreApplication.translate("Window", "Task cancelled. Your edits are preserved."))

    @override
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if any(url.isLocalFile() for url in event.mimeData().urls()) and not self.tasks.busy:
            self.preview.set_drop_active(True)
            event.acceptProposedAction()
        else:
            event.ignore()

    @override
    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self.preview.set_drop_active(False)
        event.accept()

    @override
    def dropEvent(self, event: QDropEvent) -> None:
        self.preview.set_drop_active(False)
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        if self.tasks.busy or not paths:
            event.ignore()
            return
        event.acceptProposedAction()
        self._drop_paths(paths)

    def _drop_paths(self, paths: list[Path]) -> None:
        if self.tasks.busy:
            return
        if self.session and all(
            p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"} for p in paths
        ):
            self.import_images(paths)
        elif self.session and paths[0].is_dir():
            pictures = [p for p in paths[0].iterdir() if p.suffix.lower() in {".png", ".jpg", ".webp"}]
            if pictures:
                self.import_images(pictures)
            else:
                self.open_path(paths[0])
        else:
            self.open_path(paths[0])

    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        if self.tasks.busy:
            self.tasks.cancel()
            self._show_message(
                QCoreApplication.translate(
                    "Window", "Stopping the current task. Close the window once it finishes."
                )
            )
            event.ignore()
        elif self._confirm_discard(self.close):
            if self.session is not None:
                self.session.close()
            event.accept()
        else:
            event.ignore()
