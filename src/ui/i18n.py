"""Qt translation loading and presentation of application messages."""

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QLibraryInfo, QLocale, QTranslator

from domain.messages import Message

_translators: list[QTranslator] = []


def configure_language(preference: str = "system") -> str:
    """Install translators using UI language preferences, not regional formatting."""
    language = preference
    if preference == "system":
        language = "en"
        for tag in QLocale.system().uiLanguages():
            match QLocale(tag).language():
                case QLocale.Language.Chinese:
                    language = "zh_CN"
                    break
                case QLocale.Language.English:
                    break
    app = QCoreApplication.instance()
    if app is None:
        raise RuntimeError("Create a QCoreApplication or QApplication before configuring translations")
    for translator in _translators:
        app.removeTranslator(translator)
    _translators.clear()
    if language == "zh_CN":
        translator = QTranslator(app)
        path = Path(__file__).with_name("translations") / "zh_CN.qm"
        if not translator.load(str(path)):
            raise FileNotFoundError(
                f"Cannot load Qt translations: {path}. Run pyside6-lrelease to rebuild it."
            )
        app.installTranslator(translator)
        _translators.append(translator)
        qt_translator = QTranslator(app)
        if qt_translator.load("qtbase_zh_CN", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
            app.installTranslator(qt_translator)
            _translators.append(qt_translator)
    return language


def render_message(value: str | Message | BaseException) -> str:
    """Translate a known template before formatting; external text stays verbatim."""
    if isinstance(value, BaseException):
        value = value.args[0] if value.args and isinstance(value.args[0], Message) else str(value)
    if isinstance(value, Message):
        template = QCoreApplication.translate("Messages", value.source)
        return template.format(
            *(render_message(arg) if isinstance(arg, Message) else arg for arg in value.args)
        )
    return value
