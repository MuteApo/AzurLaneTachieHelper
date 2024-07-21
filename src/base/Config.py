from PySide6.QtCore import QSettings

from .Data import IconPreset


class Config:
    _settings = QSettings("./config.ini", QSettings.Format.IniFormat)
    _default = {
        "system/AdbPath": "3rdparty/adb.exe",
        "system/DeviceAddress": "127.0.0.1",
        "system/DevicePort": "auto",
        "system/Server": "CN",
        "system/RecentPath": "",
        "system/AdvancedMode": False,
    }

    @classmethod
    def init(cls):
        for k, v in cls._default.items():
            if k not in cls._settings.allKeys():
                cls._settings.setValue(k, v)

    @classmethod
    def get(cls, group: str, key: str):
        match value := cls._settings.value(f"{group}/{key}"):
            case "true":
                return True
            case "false":
                return False
            case _:
                return value

    @classmethod
    def set(cls, group: str, key: str, value):
        cls._settings.setValue(f"{group}/{key}", value)

    @classmethod
    def get_presets(cls, group: str) -> dict[str, IconPreset]:
        presets = IconPreset.defaults()
        cls._settings.beginGroup(group)
        for k in cls._settings.childKeys():
            presets[k].from_repr(cls._settings.value(k))
        cls._settings.endGroup()
        return presets

    @classmethod
    def set_presets(cls, group: str, presets: dict[str, IconPreset]):
        cls._settings.beginGroup(group)
        for k, v in presets.items():
            cls._settings.setValue(k, v.__repr__())
        cls._settings.endGroup()
