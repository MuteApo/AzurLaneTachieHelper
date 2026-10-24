"""Flat asset navigation and small, reusable previews for the sidebar."""

from typing import override

from PySide6.QtCore import QCoreApplication, QModelIndex, QObject, QRect, QSize, QSortFilterProxyModel, Qt
from PySide6.QtGui import QFont, QIcon, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from domain.model import Asset, Kind

ASSET_KEY = Qt.ItemDataRole.UserRole
ASSET_KIND = ASSET_KEY + 1
ASSET_SUBTITLE = ASSET_KEY + 2
ASSET_MODIFIED = ASSET_KEY + 3
THUMBNAIL_SIZE = 72
THUMBNAIL_PIXELS = THUMBNAIL_SIZE * 2


class AssetFilter(QSortFilterProxyModel):
    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._kind: Kind | None = None
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def set_kind(self, kind: Kind | None) -> None:
        self.beginFilterChange()
        self._kind = kind
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    @override
    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        index = self.sourceModel().index(source_row, 0, source_parent)
        if self._kind is not None and index.data(ASSET_KIND) != self._kind:
            return False
        text = " ".join(
            str(index.data(role) or "") for role in (Qt.ItemDataRole.DisplayRole, ASSET_SUBTITLE, ASSET_KEY)
        )
        return self.filterRegularExpression().match(text).hasMatch()


class AssetDelegate(QStyledItemDelegate):
    """Paint thumbnail rows without creating a widget for every asset."""

    @override
    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        return QSize(218, THUMBNAIL_SIZE + 22)

    @override
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        palette = option.palette
        bounds = option.rect.adjusted(1, 2, -1, -2)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        focused = bool(option.state & QStyle.StateFlag.State_HasFocus)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        painter.setPen(Qt.PenStyle.NoPen)
        if selected or hovered:
            background = QPalette.ColorRole.Highlight if selected else QPalette.ColorRole.AlternateBase
            painter.setBrush(palette.brush(background))
            if selected:
                painter.setPen(QPen(palette.color(QPalette.ColorRole.Mid), 1))
            painter.drawRoundedRect(bounds, 9, 9)
        if focused:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(palette.color(QPalette.ColorRole.Link), 1))
            painter.drawRoundedRect(bounds, 9, 9)

        thumbnail = QRect(
            bounds.left() + 9, bounds.center().y() - THUMBNAIL_SIZE // 2, THUMBNAIL_SIZE, THUMBNAIL_SIZE
        )
        decoration = index.data(Qt.ItemDataRole.DecorationRole)
        image = (
            decoration.pixmap(THUMBNAIL_PIXELS, THUMBNAIL_PIXELS)
            if isinstance(decoration, QIcon)
            else decoration
        )
        if isinstance(image, QPixmap) and not image.isNull():
            size = image.size().scaled(thumbnail.size(), Qt.AspectRatioMode.KeepAspectRatio)
            target = QRect(0, 0, size.width(), size.height())
            target.moveCenter(thumbnail.center())
            painter.drawPixmap(target, image)

        left = thumbnail.right() + 12
        width = max(0, bounds.right() - left - 12)
        modified = bool(index.data(ASSET_MODIFIED))
        font = QFont(option.font)
        font.setPixelSize(13)
        painter.setFont(font)
        painter.setPen(palette.color(QPalette.ColorRole.Text))
        title = painter.fontMetrics().elidedText(
            str(index.data(Qt.ItemDataRole.DisplayRole) or ""),
            Qt.TextElideMode.ElideRight,
            max(0, width - (12 if modified else 0)),
        )
        title_rect = QRect(left, bounds.center().y() - 20, width, 22)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignVCenter, title)
        if modified:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(palette.brush(QPalette.ColorRole.Link))
            painter.drawEllipse(bounds.right() - 14, title_rect.center().y() - 2, 4, 4)
        font.setPixelSize(11)
        painter.setFont(font)
        painter.setPen(palette.color(QPalette.ColorRole.PlaceholderText))
        subtitle = painter.fontMetrics().elidedText(
            str(index.data(ASSET_SUBTITLE) or ""), Qt.TextElideMode.ElideRight, width
        )
        painter.drawText(
            QRect(left, bounds.center().y() + 3, width, 19), Qt.AlignmentFlag.AlignVCenter, subtitle
        )
        painter.restore()


def image_name(asset: Asset) -> str:
    if asset.kind == Kind.FACE:
        return QCoreApplication.translate("Window", "Expression {0}").format(asset.name)
    if asset.kind == Kind.ICON:
        names = {
            "shipyardicon": QCoreApplication.translate("Window", "Dock portrait"),
            "herohrzicon": QCoreApplication.translate("Window", "Wide portrait"),
            "squareicon": QCoreApplication.translate("Window", "Square portrait"),
        }
        return names.get(asset.name, asset.name)
    return asset.name
