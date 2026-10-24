"""Language selection and dynamic UI text, including Qt's own standard buttons."""

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication, QLocale
from PySide6.QtWidgets import QApplication, QMessageBox

from adapters.storage import Settings
from domain.messages import Message
from ui.dialogs.preferences import PreferencesDialog
from ui.i18n import configure_language, render_message
from ui.studio.window import MainWindow


@pytest.fixture
def app():
    application = QApplication.instance() or QApplication([])
    configure_language("en")
    yield application
    configure_language("system")


def test_system_language_and_explicit_override(app, monkeypatch):
    monkeypatch.setattr(QLocale, "system", lambda: QLocale("zh_TW"))
    assert configure_language("system") == "zh_CN"
    assert QCoreApplication.translate("Dialogs", "Save") == "保存"
    assert configure_language("en") == "en"
    assert QCoreApplication.translate("Dialogs", "Save") == "Save"
    monkeypatch.setattr(QLocale, "system", lambda: QLocale("ja_JP"))
    assert configure_language("system") == "en"
    assert QCoreApplication.translate("Dialogs", "Save") == "Save"
    assert QCoreApplication.translate("Dialogs", "Untranslated English text") == "Untranslated English text"


def test_ui_language_priority_is_independent_of_regional_format(app, monkeypatch):
    regional_locale = SimpleNamespace(
        language=lambda: QLocale.Language.English,
        uiLanguages=lambda: ["zh-Hans-CN", "en-US"],
    )
    monkeypatch.setattr(QLocale, "system", lambda: regional_locale)
    assert configure_language() == "zh_CN"
    assert QCoreApplication.translate("Dialogs", "Save") == "保存"
    assert configure_language("en") == "en"
    regional_locale.uiLanguages = lambda: ["en-US", "zh-Hans-CN"]
    assert configure_language() == "en"
    assert QCoreApplication.translate("Dialogs", "Save") == "Save"


def test_ui_language_is_saved_for_next_start_and_translates_progress(app, tmp_path):
    settings = Settings(tmp_path / "settings.json")
    window = MainWindow(settings)
    assert window.open_action.text() == "Open resources…"
    window._progress(Message("Reading {0}", ("中文资源 {layer}",)), 1, 2)
    assert window.feedback_text.text() == "Reading 中文资源 {layer}"
    assert render_message(Message("import {0} images", (3,))) == "import 3 images"
    assert (
        render_message(
            FileNotFoundError(
                Message("Project dependencies are missing:\n{0}", ("painting/中文资源 {file}",))
            )
        )
        == "Project dependencies are missing:\npainting/中文资源 {file}"
    )
    # Third-party text is displayed verbatim even if it resembles an application template.
    raw = "读取 中文资源 {layer}"
    assert render_message(raw) == raw
    assert render_message(ValueError(raw)) == raw
    window._progress(raw, 1, 2)
    assert window.feedback_text.text() == raw
    preferences = PreferencesDialog(settings, window)
    preferences.language.setCurrentIndex(preferences.language.findData("zh_CN"))
    preferences.accept()
    assert settings.data.language == "zh_CN"
    assert QCoreApplication.translate("Dialogs", "Save") == "Save"
    window.close()

    configure_language(settings.data.language)
    restarted = MainWindow(settings)
    assert restarted.open_action.text() == "打开资源…"
    restarted._progress(Message("Reading {0}", ("中文资源 {layer}",)), 1, 2)
    assert restarted.feedback_text.text() == "读取 中文资源 {layer}"
    assert render_message(Message("import {0} images", (3,))) == "导入 3 张图片"
    assert render_message("Reading unstructured text") == "Reading unstructured text"
    box = QMessageBox(restarted)
    box.setStandardButtons(QMessageBox.StandardButton.Cancel)
    assert "取消" in box.button(QMessageBox.StandardButton.Cancel).text()
    restarted.close()


@pytest.mark.parametrize(
    "language, expected", [("en", "list assets in the terminal"), ("zh_CN", "在终端列出资源，不启动窗口")]
)
def test_cli_help_uses_saved_language_without_starting_gui(tmp_path, language, expected):
    Settings(tmp_path / "settings.json").set("language", language)
    environment = {**os.environ, "PYTHONUTF8": "1", "PYTHONPATH": str(Path(__file__).parents[1] / "src")}
    # A nonexistent GUI platform catches accidental QApplication initialization in the CLI path.
    environment["QT_QPA_PLATFORM"] = "not-a-platform"
    result = subprocess.run(
        [sys.executable, "-m", "main", "--data-dir", str(tmp_path), "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert expected in result.stdout
    assert not (tmp_path / "logs").exists()
