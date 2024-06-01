from PySide6.QtCore import QSettings

from .Data import IconPreset
from .Vector import Vector2

settings = QSettings("./config.ini", QSettings.Format.IniFormat)


class Config:
    @staticmethod
    def get_bool(key: str, default: bool = False) -> bool:
        value = {True: "true", False: "false"}[default]
        return eval(str(settings.value(key, value)).capitalize())

    @staticmethod
    def get_str(key: str, default: str = "") -> str:
        value = settings.value(key, default)
        if value == default:
            Config.set(key, value)
        return value

    @staticmethod
    def get_vec2(key: str, default: Vector2 = Vector2(0, 0)) -> Vector2:
        return settings.value(key, default)

    @staticmethod
    def set(key: str, value):
        settings.setValue(key, value)

    @staticmethod
    def get_presets(prefix: str) -> dict[str, IconPreset]:
        settings.beginGroup(prefix)
        presets = IconPreset.defaults()
        for k, v in presets.items():
            v.from_repr(settings.value(k, presets[k].__repr__()))
        settings.endGroup()
        return presets

    @staticmethod
    def set_presets(prefix: str, presets: dict[str, IconPreset]):
        settings.beginGroup(prefix)
        for k, v in presets.items():
            settings.setValue(k, v.__repr__())
        settings.endGroup()
