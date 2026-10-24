from PySide6.QtCore import QCoreApplication, QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from domain.model import FaceMode, Kind, Project
from ui.studio.assets import image_name
from ui.widgets.controls import SegmentedChoice, button, label, with_icon


class InspectorPanel(QWidget):
    psd_requested = Signal()
    import_requested = Signal()
    portrait_requested = Signal()
    replace_requested = Signal()
    reset_requested = Signal()
    original_changed = Signal()
    options_changed = Signal(object)
    extensions_changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._updating = False
        self.task_tools = QWidget()
        task_row = QVBoxLayout(self.task_tools)
        task_row.setContentsMargins(0, 0, 0, 0)
        task_row.setSpacing(4)
        self.psd_button = button(
            QCoreApplication.translate("Window", "Export layered image (PSD)"),
            lambda: self.psd_requested.emit(),
        )
        self.import_button = button(
            QCoreApplication.translate("Window", "Replace multiple images…"),
            lambda: self.import_requested.emit(),
        )
        self.crop_button = button(
            QCoreApplication.translate("Window", "Create portraits…"), lambda: self.portrait_requested.emit()
        )
        self.psd_button.setToolTip(
            QCoreApplication.translate("Window", "Save separate layers for editing in a painting app.")
        )
        self.import_button.setToolTip(
            QCoreApplication.translate(
                "Window", "Choose your edited PNG images and match them to the artwork."
            )
        )
        self.crop_button.setToolTip(
            QCoreApplication.translate("Window", "Crop a full artwork image into the three portrait sizes.")
        )
        for widget, glyph in (
            (self.psd_button, "layers"),
            (self.import_button, "replace"),
            (self.crop_button, "crop"),
        ):
            widget.setObjectName("rowAction")
            with_icon(widget, glyph)
            task_row.addWidget(widget)

        self.preview_version = SegmentedChoice(
            [
                (QCoreApplication.translate("Window", "With edits"), False),
                (QCoreApplication.translate("Window", "Before edits"), True),
            ]
        )
        self.preview_version.setToolTip(
            QCoreApplication.translate("Window", "Compare your changes with the unedited images.")
        )
        self.preview_version.currentIndexChanged.connect(lambda: self.original_changed.emit())
        self.setObjectName("inspector")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(264)
        self.setMaximumWidth(350)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner.setObjectName("rail")
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(20, 22, 20, 20)
        layout.setSpacing(12)
        layout.addWidget(label(QCoreApplication.translate("Window", "Next steps")))
        layout.addWidget(self.task_tools)
        rule = QFrame()
        rule.setObjectName("rule")
        rule.setFixedHeight(1)
        layout.addWidget(rule)
        layout.addWidget(label(QCoreApplication.translate("Window", "Selected image")))
        self.asset_name = label(QCoreApplication.translate("Window", "No layer selected"), "title")
        self.asset_name.setWordWrap(True)
        self.asset_info = label(
            QCoreApplication.translate("Window", "Select an asset to view its source and edit status.")
        )
        self.asset_info.setWordWrap(True)
        self.asset_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.asset_name)
        layout.addWidget(self.asset_info)
        self.replace_button = button(
            QCoreApplication.translate("Window", "Replace…"), lambda: self.replace_requested.emit()
        )
        self.replace_button.setToolTip(QCoreApplication.translate("Window", "Replace this image…"))
        self.replace_button.setObjectName("secondary")
        with_icon(self.replace_button, "replace")
        self.reset_button = button(
            QCoreApplication.translate("Window", "Restore"), lambda: self.reset_requested.emit()
        )
        self.reset_button.setToolTip(QCoreApplication.translate("Window", "Restore original image"))
        self.reset_button.setObjectName("quiet")
        image_actions = QHBoxLayout()
        image_actions.setSpacing(8)
        image_actions.addWidget(self.replace_button, 1)
        image_actions.addWidget(self.reset_button)
        layout.addLayout(image_actions)
        layout.addWidget(self.preview_version)
        rule = QFrame()
        rule.setObjectName("rule")
        rule.setFixedHeight(1)
        layout.addWidget(rule)
        layout.addSpacing(12)
        basic_layout = layout
        basic_layout.addWidget(label(QCoreApplication.translate("Window", "Advanced settings")))
        self.advanced_panel = QWidget()
        layout = QVBoxLayout(self.advanced_panel)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(12)
        basic_layout.addWidget(self.advanced_panel)
        advanced_heading = label(
            QCoreApplication.translate("Window", "Expression bounds & image decoding"), "heading"
        )
        advanced_heading.setWordWrap(True)
        layout.addWidget(advanced_heading)
        self.face_mode = QComboBox()
        for name, mode in [
            (QCoreApplication.translate("Window", "Off · Original bounds"), FaceMode.OFF),
            (QCoreApplication.translate("Window", "Auto · Expand expressions"), FaceMode.AUTO),
            (QCoreApplication.translate("Window", "Custom · Adjust bounds"), FaceMode.CUSTOM),
        ]:
            self.face_mode.addItem(name, mode)
        self.face_mode.currentIndexChanged.connect(self._options)
        layout.addWidget(self.face_mode)
        self.extension_widget = QWidget()
        extensions = QGridLayout(self.extension_widget)
        extensions.setContentsMargins(0, 0, 0, 0)
        extensions.setHorizontalSpacing(8)
        extensions.setColumnStretch(0, 1)
        extensions.setColumnStretch(1, 1)
        self.extensions: list[QSpinBox] = []
        for i, title in enumerate(
            (
                QCoreApplication.translate("Window", "Left Δ"),
                QCoreApplication.translate("Window", "Bottom Δ"),
                QCoreApplication.translate("Window", "Right Δ"),
                QCoreApplication.translate("Window", "Top Δ"),
            )
        ):
            field = QSpinBox()
            field.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            field.setRange(-100000, 100000)
            field.setSingleStep(25)
            field.setKeyboardTracking(False)
            field.valueChanged.connect(self._extensions)
            extensions.addWidget(label(title), i // 2 * 2, i % 2)
            extensions.addWidget(field, i // 2 * 2 + 1, i % 2)
            self.extensions.append(field)
        layout.addWidget(self.extension_widget)
        self.extension_widget.hide()
        layout.addSpacing(12)
        layout.addWidget(label(QCoreApplication.translate("Window", "Output"), "heading"))
        self.compression = QComboBox()
        for name, value in [
            (QCoreApplication.translate("Window", "Bundle · Original compression"), "original"),
            (QCoreApplication.translate("Window", "Bundle · LZ4 compression"), "lz4"),
            (QCoreApplication.translate("Window", "Bundle · Uncompressed"), "none"),
        ]:
            self.compression.addItem(name, value)
        self.compression.currentIndexChanged.connect(self._options)
        for choice in (self.face_mode, self.compression):
            choice.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            choice.setMinimumContentsLength(1)
        layout.addWidget(self.compression)
        basic_layout.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll)

    def set_asset(self, project: Project, selected_key: str | None) -> None:
        self._updating = True
        options = project.options
        self.face_mode.setCurrentIndex(self.face_mode.findData(options.face_mode))
        self.compression.setCurrentIndex(self.compression.findData(options.compression))
        asset = project.asset(selected_key) if selected_key else None
        if asset:
            self.asset_name.setText(image_name(asset))
            self.asset_info.setText(
                QCoreApplication.translate("Window", "Replaced")
                if asset.modified
                else QCoreApplication.translate("Window", "Original assets")
            )
            self.asset_info.setToolTip(
                QCoreApplication.translate("Window", "Bundle: {0}\nObject: {1}").format(
                    asset.texture.bundle, asset.texture.path_id
                )
            )
            extension_key = "paintingface" if asset.kind == Kind.FACE else asset.key
            for field, value in zip(self.extensions, options.extensions.get(extension_key, (0, 0, 0, 0))):
                field.setValue(value)
        custom = options.face_mode == FaceMode.CUSTOM
        self.extension_widget.setVisible(custom)
        self.extension_widget.setEnabled(asset is not None and asset.kind != Kind.ICON)
        self._updating = False

    def _options(self) -> None:
        if not self._updating:
            self.options_changed.emit(
                {
                    "face_mode": self.face_mode.currentData(),
                    "compression": self.compression.currentData(),
                }
            )

    def _extensions(self) -> None:
        if not self._updating:
            self.extensions_changed.emit(tuple(field.value() for field in self.extensions))

    def set_available(self, project: Project | None, selected_key: str | None, idle: bool) -> None:
        self.setEnabled(project is not None and idle)
        asset = project.asset(selected_key) if project and selected_key else None
        self.replace_button.setEnabled(idle and asset is not None)
        self.reset_button.setEnabled(idle and asset is not None and asset.modified)
        self.reset_button.setVisible(asset is not None and asset.modified)
        self.crop_button.setEnabled(idle and project is not None and project.face is not None)
        self.preview_version.setVisible(project is not None and bool(project.modified))

    @property
    def showing_original(self) -> bool:
        return self.preview_version.currentData()

    def show_edits(self) -> None:
        """Reset comparison without requesting a preview before the edit finishes."""
        with QSignalBlocker(self.preview_version):
            self.preview_version.setCurrentData(False)
