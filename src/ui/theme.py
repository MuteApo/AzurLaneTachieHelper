"""Shared Geist-inspired surfaces and controls for the native Qt workbench.

Monochrome actions, quiet lavender selection, and continuous workspace rails.
"""

from pathlib import Path
from string import Template

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# Each role contains its dark and light variants.
COLORS = {
    "text": ("#ececef", "#232329"),
    "soft_text": ("#c7c7ce", "#44444c"),
    "background": ("#101012", "#f3f3f5"),
    "surface": ("#151517", "#fcfcfd"),
    "header": ("#151517", "#fcfcfd"),
    "border": ("#2c2c31", "#e4e4e9"),
    "title": ("#ececef", "#232329"),
    "accent": ("#b6a6e8", "#76639f"),
    "muted": ("#929299", "#73737c"),
    "selected": ("#25232f", "#eeebf6"),
    "selected_border": ("#494257", "#c9bfdf"),
    "selected_text": ("#ececef", "#232329"),
    "button": ("#222225", "#f0f0f3"),
    "hover": ("#222225", "#f0f0f3"),
    "hover_border": ("#4b4b53", "#bcbcc6"),
    "pressed": ("#303036", "#e4e4e9"),
    "active": ("#303036", "#ffffff"),
    "primary": ("#ececef", "#232329"),
    "primary_text": ("#151517", "#fcfcfd"),
    "primary_hover": ("#c7c7ce", "#44444c"),
    "primary_pressed": ("#a9a9b2", "#111113"),
    "disabled_text": ("#66666f", "#a0a0aa"),
    "disabled": ("#1d1d20", "#ececef"),
    "input": ("#111113", "#f0f0f3"),
    "popup": ("#1c1c1f", "#fcfcfd"),
    "alternate": ("#222225", "#e9e9ed"),
    "scroll": ("#44444c", "#c4c4ce"),
    "track": ("#303036", "#dedee5"),
    "handle": ("#b6a6e8", "#76639f"),
    "focus": ("#b6a6e8", "#76639f"),
    "danger": ("#c42b1c", "#c42b1c"),
    "danger_text": ("#ffffff", "#ffffff"),
}

_STYLESHEET = Template("""
QWidget { color: ${text}; font-family: 'Microsoft YaHei UI', 'Segoe UI', sans-serif;
          font-size: 13px; }
QMainWindow { background: ${background}; }
QDialog { background: ${surface}; }
QWidget#header { background: ${header}; border-bottom: 1px solid ${border}; }
QWidget#panel { background: ${surface}; border-radius: 8px; }
QWidget#sidebar { background: ${surface}; border-right: 1px solid ${border}; }
QWidget#inspector { background: ${surface}; border-left: 1px solid ${border}; }
QWidget#rail { background: ${surface}; }
QWidget#viewport { background: ${background}; }
QWidget#notice { background: ${selected}; border: 1px solid ${border}; border-radius: 8px; }
QLabel { background: transparent; border: none; }
QLabel#brand { color: ${title}; font-size: 16px; font-weight: 600; }
QLabel#mark { color: ${surface}; background: ${text}; border-radius: 8px; font-size: 17px; font-weight: 700; }
QPushButton#appMenu { color: ${surface}; background: ${text}; border: 1px solid transparent;
    border-radius: 8px; font-size: 17px; font-weight: 700; padding: 0; }
QPushButton#appMenu:hover { background: ${soft_text}; }
QPushButton#appMenu:focus { border-color: ${focus}; }
QLabel#heading { color: ${title}; font-size: 13px; font-weight: 600; }
QLabel#title { color: ${title}; font-size: 18px; font-weight: 600; }
QLabel#muted { color: ${muted}; }
QLabel#caption, QLabel#subtle { color: ${muted}; font-size: 12px; }
QLabel#eyebrow { color: ${muted}; font-size: 11px; }
QLabel#emptyTitle { color: ${title}; font-size: 28px; font-weight: 600; }
QLabel#badge { color: ${muted}; background: ${hover}; font-size: 11px; padding: 2px 6px; border-radius: 4px; }
QFrame#rule { background: ${border}; border: none; max-height: 1px; }
QPushButton, QToolButton { background: ${button}; border: 1px solid ${border};
    border-radius: 7px; padding: 7px 10px; min-height: 18px; }
QToolButton { background: transparent; border-color: transparent; padding: 6px 8px; }
QPushButton:hover, QToolButton:hover { background: ${hover}; border-color: ${hover_border}; }
QPushButton:pressed, QToolButton:pressed { background: ${pressed}; }
QPushButton:checked, QToolButton:checked { background: ${selected}; border-color: ${selected_border}; color: ${selected_text}; }
QPushButton#primary { color: ${primary_text}; background: ${primary}; border-color: ${primary}; font-weight: 600; }
QPushButton#primary:hover { background: ${primary_hover}; }
QPushButton#primary:pressed { background: ${primary_pressed}; }
QPushButton:focus, QToolButton:focus { border-color: ${focus}; }
QPushButton#secondary { background: ${button}; border-color: ${border}; color: ${text}; }
QPushButton#secondary:hover { background: ${pressed}; border-color: ${hover_border}; }
QPushButton#quiet, QPushButton#rowAction, QPushButton#assetFilter,
QToolButton#quiet { background: transparent; border-color: transparent; color: ${muted}; }
QPushButton#rowAction { text-align: left; color: ${text}; padding: 10px 12px; }
QPushButton#quiet:hover, QPushButton#rowAction:hover, QPushButton#assetFilter:hover,
QToolButton#quiet:hover { background: ${hover}; color: ${text}; }
QPushButton#quiet:focus, QPushButton#rowAction:focus, QPushButton#assetFilter:focus,
QToolButton#quiet:focus { border-color: ${focus}; }
QPushButton#assetFilter { padding: 5px 7px; }
QPushButton#assetFilter:checked { background: ${hover}; color: ${text}; }
QWidget#segment { background: ${input}; border: 1px solid ${border}; border-radius: 9px; }
QPushButton#segmentOption { background: transparent; border-color: transparent; border-radius: 6px;
    color: ${muted}; padding: 5px 10px; }
QPushButton#segmentOption:hover { background: ${hover}; color: ${text}; }
QPushButton#segmentOption:checked { background: ${active}; color: ${text}; }
QPushButton#segmentOption:focus { border-color: ${focus}; }
QWidget#assetFilter QPushButton { padding: 5px 4px; font-size: 12px; }
QWidget#zoomBar { background: ${surface}; border: 1px solid ${border}; border-radius: 11px; }
QWidget#zoomBar QPushButton, QWidget#zoomBar QToolButton { background: transparent; border-color: transparent; }
QWidget#zoomBar QPushButton:hover, QWidget#zoomBar QToolButton:hover { background: ${hover}; }
QWidget#zoomBar QPushButton:focus, QWidget#zoomBar QToolButton:focus { border-color: ${focus}; }
QPushButton[welcomeAction="true"] { text-align: left; padding: 20px; }
QPushButton#recentItem { text-align: left; padding: 12px; }
QPushButton#primary:disabled { color: ${disabled_text}; background: ${disabled}; border-color: ${disabled}; }
QPushButton:disabled, QToolButton:disabled { color: ${disabled_text}; background: ${disabled}; border-color: ${disabled}; }
QPushButton#quiet:disabled, QPushButton#rowAction:disabled, QPushButton#assetFilter:disabled,
QPushButton#segmentOption:disabled, QToolButton#quiet:disabled { color: ${disabled_text}; background: transparent; border-color: transparent; }
QPushButton#secondary:disabled { color: ${disabled_text}; background: ${disabled}; border-color: ${disabled}; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: ${input}; border: 1px solid ${border};
    border-radius: 7px; padding: 7px 9px; min-height: 18px; selection-background-color: ${selected}; selection-color: ${selected_text}; }
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover { border-color: ${hover_border}; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color: ${accent}; }
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled { color: ${disabled_text}; background: ${disabled}; }
QComboBox QAbstractItemView { background: ${popup}; selection-background-color: ${selected}; selection-color: ${selected_text}; }
QComboBox QLineEdit { border: none; padding: 0; background: transparent; }
QAbstractItemView#completionPopup { background: ${popup}; border: 1px solid ${border};
    selection-background-color: ${selected}; selection-color: ${selected_text}; }
QListView#completionPopup::item { min-height: 24px; padding: 4px 10px; }
QComboBox { padding-right: 28px; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 24px; border: none; }
QComboBox::down-arrow { image: url("${arrow_down}"); width: 16px; height: 16px; }
QSpinBox, QDoubleSpinBox { padding-right: 24px; }
QSpinBox::up-button, QDoubleSpinBox::up-button { subcontrol-origin: border; subcontrol-position: top right;
    width: 22px; border: none; border-left: 1px solid ${border}; border-top-right-radius: 7px; }
QSpinBox::down-button, QDoubleSpinBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right;
    width: 22px; border: none; border-left: 1px solid ${border}; border-bottom-right-radius: 7px; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover { background: ${hover}; }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow { image: url("${arrow_up}"); width: 12px; height: 12px; }
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { image: url("${arrow_down}"); width: 12px; height: 12px; }
QTreeView, QListView, QTableWidget { background: transparent; border: none; outline: none;
    alternate-background-color: ${alternate}; }
QTreeView::item { padding: 8px 4px; border-radius: 6px; border: 1px solid transparent; }
QTreeView::item:selected { background: ${selected}; color: ${selected_text}; border-color: ${selected_border}; }
QTreeView::item:hover:!selected { background: ${hover}; }
QListView::item:selected, QTableWidget::item:selected { background: ${selected}; color: ${selected_text}; }
QHeaderView::section { background: ${alternate}; color: ${muted}; border: none; padding: 8px; font-size: 12px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 6px; margin: 0; }
QScrollBar::handle:vertical { background: ${scroll}; min-height: 30px; border-radius: 3px; }
QScrollBar:horizontal { background: transparent; height: 6px; }
QScrollBar::handle:horizontal { background: ${scroll}; min-width: 30px; border-radius: 3px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QSplitter::handle { background: transparent; }
QSplitter::handle:hover { background: ${selected_border}; }
QPushButton#statusAction { background: transparent; border-color: transparent; padding: 2px 8px;
    min-height: 16px; font-size: 12px; }
QPushButton#statusAction:hover { background: ${hover}; }
QPushButton#statusAction:focus { border-color: ${focus}; }
QProgressBar { background: ${track}; border: none; border-radius: 3px; height: 6px; }
QProgressBar::chunk { background: ${accent}; border-radius: 3px; }
QMenu::item:selected { background: ${selected}; color: ${text}; }
QMenu { background: ${popup}; border: 1px solid ${border}; padding: 4px; }
QMenu::item { padding: 8px 24px; border-radius: 6px; }
QMenu::separator { height: 1px; background: ${border}; margin: 4px 8px; }
QPlainTextEdit { background: ${input}; border: 1px solid ${border}; border-radius: 7px; padding: 6px; }
QCheckBox { spacing: 8px; }
QCheckBox:disabled { color: ${disabled_text}; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid ${hover_border}; border-radius: 4px; background: ${input}; }
QCheckBox::indicator:hover { border-color: ${text}; }
QCheckBox::indicator:checked { background: ${accent}; border-color: ${accent}; image: url("${checkmark}"); }
QCheckBox::indicator:focus { border: 1px solid ${focus}; }
QCheckBox::indicator:disabled { background: ${disabled}; border-color: ${border}; }
QSlider::groove:horizontal { height: 5px; border-radius: 2px; background: ${track}; }
QSlider::sub-page:horizontal { background: ${accent}; border-radius: 2px; }
QSlider::handle:horizontal { width: 13px; margin: -4px 0; border-radius: 6px; background: ${handle}; }
QGroupBox { border: 1px solid ${border}; border-radius: 8px; margin-top: 16px; padding-top: 12px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; color: ${muted}; }
QToolTip { background: ${popup}; color: ${title}; border: 1px solid ${hover_border}; padding: 6px; }
""")


def apply_theme(app: QApplication, scheme: Qt.ColorScheme) -> None:
    # Platforms without a color-scheme hint use the light theme.
    index = 0 if scheme == Qt.ColorScheme.Dark else 1
    colors = {role: variants[index] for role, variants in COLORS.items()}
    palette = QPalette()
    for role, name in {
        QPalette.ColorRole.Window: "background",
        QPalette.ColorRole.WindowText: "text",
        QPalette.ColorRole.Base: "input",
        QPalette.ColorRole.AlternateBase: "alternate",
        QPalette.ColorRole.Mid: "selected_border",
        QPalette.ColorRole.Text: "text",
        QPalette.ColorRole.Button: "button",
        QPalette.ColorRole.ButtonText: "text",
        QPalette.ColorRole.Highlight: "selected",
        QPalette.ColorRole.HighlightedText: "selected_text",
        QPalette.ColorRole.Link: "accent",
        QPalette.ColorRole.PlaceholderText: "muted",
        QPalette.ColorRole.ToolTipBase: "popup",
        QPalette.ColorRole.ToolTipText: "text",
    }.items():
        palette.setColor(role, QColor(colors[name]))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(colors["disabled_text"]))
    app.setPalette(palette)
    icons = Path(__file__).with_name("icons")
    variant = "dark" if index == 0 else "light"
    glyphs = {
        name: (icons / f"{name}-{variant}.svg").as_posix() for name in ("arrow_down", "arrow_up", "checkmark")
    }
    app.setStyleSheet(_STYLESHEET.substitute(colors, **glyphs))
