from PIL import Image
from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtGui import (
    QIcon,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLineEdit,
    QListView,
    QVBoxLayout,
    QWidget,
)

from domain.model import Kind, Project
from ui.studio.assets import (
    ASSET_KIND,
    ASSET_MODIFIED,
    ASSET_SUBTITLE,
    AssetDelegate,
    AssetFilter,
    image_name,
)
from ui.widgets.canvas import pixmap
from ui.widgets.controls import SegmentedChoice, button, label, with_icon


class AssetSidebar(QWidget):
    open_requested = Signal()
    selection_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_key: str | None = None
        self._updating = False
        self._modified_count = 0
        self._thumbnail_icons: dict[str, QIcon] = {}
        self.setObjectName("sidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(238)
        self.setMaximumWidth(380)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 20, 14, 16)
        layout.setSpacing(12)
        title = QHBoxLayout()
        title.addWidget(label(QCoreApplication.translate("Window", "Images"), "heading"))
        self.count = label("0", "badge")
        title.addWidget(self.count)
        title.addStretch()
        self.open_button = with_icon(button("", lambda: self.open_requested.emit()), "folder")
        self.open_button.setToolTip(QCoreApplication.translate("Window", "Open resources"))
        self.open_button.setAccessibleName(self.open_button.toolTip())
        self.open_button.setObjectName("quiet")
        title.addWidget(self.open_button)
        layout.addLayout(title)
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText(QCoreApplication.translate("Window", "Search images…"))
        layout.addWidget(self.search)
        self.model = QStandardItemModel(self)
        self.proxy = AssetFilter(self)
        self.proxy.setSourceModel(self.model)
        self.asset_filter = SegmentedChoice[Kind | None](
            [
                (QCoreApplication.translate("Window", "All"), None),
                (QCoreApplication.translate("Window", "Artwork"), Kind.PAINTING),
                (QCoreApplication.translate("Window", "Faces"), Kind.FACE),
                (QCoreApplication.translate("Window", "Portraits"), Kind.ICON),
            ]
        )
        self.asset_filter.setObjectName("assetFilter")
        self.asset_filter.currentIndexChanged.connect(self._filter_assets)
        layout.addWidget(self.asset_filter)
        self.tree = QListView()
        self.tree.setModel(self.proxy)
        self.tree.setItemDelegate(AssetDelegate(self.tree))
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setUniformItemSizes(True)
        self.tree.setMouseTracking(True)
        self.tree.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tree.selectionModel().currentChanged.connect(self._selected)
        self.search.textChanged.connect(self._filter_assets)
        layout.addWidget(self.tree, 1)
        self.asset_summary = label(
            QCoreApplication.translate(
                "Window", "Open a project to browse artwork, expressions and portraits."
            )
        )
        self.asset_summary.setWordWrap(True)
        layout.addWidget(self.asset_summary)

    def _filter_assets(self, *args):
        self._updating = True
        self.proxy.set_kind(self.asset_filter.currentData())
        self.proxy.setFilterFixedString(self.search.text())
        selected = next(
            (
                self.model.item(row)
                for row in range(self.model.rowCount())
                if self.model.item(row).data(Qt.ItemDataRole.UserRole) == self.selected_key
            ),
            None,
        )
        if selected:
            self.tree.setCurrentIndex(self.proxy.mapFromSource(selected.index()))
        self._updating = False
        # Filtering narrows navigation without changing the image being edited.
        self._update_asset_summary()

    def _update_asset_summary(self):
        self.asset_summary.setText(
            QCoreApplication.translate("Window", "No matching images")
            if not self.proxy.rowCount()
            else QCoreApplication.translate("Window", "{0} images replaced").format(self._modified_count)
        )

    def set_project(self, project: Project, selected_key: str | None) -> str | None:
        self.selected_key = selected_key
        self._modified_count = len(project.modified)
        self._updating = True
        self.model.clear()
        selected = None
        for kind, title in [
            (Kind.PAINTING, QCoreApplication.translate("Window", "Artwork")),
            (Kind.FACE, QCoreApplication.translate("Window", "Expressions")),
            (Kind.ICON, QCoreApplication.translate("Window", "Portraits")),
        ]:
            assets = [a for a in project.assets if a.kind == kind]
            if not assets:
                continue
            for asset in assets:
                item = QStandardItem(image_name(asset))
                item.setData(asset.key, Qt.ItemDataRole.UserRole)
                item.setData(asset.kind, ASSET_KIND)
                item.setData(title, ASSET_SUBTITLE)
                item.setData(asset.modified, ASSET_MODIFIED)
                if asset.key in self._thumbnail_icons:
                    item.setIcon(self._thumbnail_icons[asset.key])
                item.setToolTip(f"{asset.name}\n{asset.texture.bundle}")
                self.model.appendRow(item)
                if asset.key == self.selected_key:
                    selected = item
                elif self.selected_key is None and selected is None:
                    selected = item
        if selected:
            self.selected_key = selected.data(Qt.ItemDataRole.UserRole)
            self.tree.setCurrentIndex(self.proxy.mapFromSource(selected.index()))
        self.count.setText(str(len(project.assets)))
        self._update_asset_summary()
        self._updating = False
        return self.selected_key

    def _selected(self, current, previous):
        if self._updating:
            return
        key = current.data(Qt.ItemDataRole.UserRole)
        if key:
            self.selected_key = key
            self.selection_changed.emit(key)

    def set_thumbnails(self, thumbnails: dict[str, Image.Image]) -> None:
        for row in range(self.model.rowCount()):
            item = self.model.item(row)
            key = item.data(Qt.ItemDataRole.UserRole)
            if key in thumbnails:
                thumbnail = QIcon(pixmap(thumbnails[key]))
                self._thumbnail_icons[key] = thumbnail
                item.setIcon(thumbnail)

    def clear(self) -> None:
        self.selected_key = None
        self._thumbnail_icons.clear()
        self.model.clear()
        self.search.clear()
        self.asset_filter.setCurrentIndex(0)

    def set_available(self, idle: bool) -> None:
        self.open_button.setEnabled(idle)
        self.tree.setEnabled(idle)

    def refresh_palette(self) -> None:
        self.tree.viewport().update()
