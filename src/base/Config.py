from PySide6.QtCore import QSettings

from .Data import IconPreset


class Config:
    _settings = QSettings("./config.ini", QSettings.Format.IniFormat)
    _default = {
        "system/RecentPath": "",
        "system/Compression": "original",
        "system/AdvFaceMode": "off",
        "system/AdbPath": "3rdparty/adb.exe",
        "system/DeviceAddress": "127.0.0.1",
        "system/DevicePort": "auto",
        "system/Server": "CN",
    }

    @classmethod
    def init(cls):
        for k, v in cls._default.items():
            if not cls._settings.contains(k):
                cls._settings.setValue(k, v)

    @classmethod
    def get(cls, group: str, key: str):
        value = cls._settings.value(f"{group}/{key}")
        if value == "true":
            return True
        elif value == "false":
            return False
        return value

    @classmethod
    def set(cls, group: str, key: str, value):
        cls._settings.setValue(f"{group}/{key}", value)
        return cls.get(group, key)

    @classmethod
    def get_presets(cls, group: str) -> dict[str, IconPreset]:
        presets = {}
        cls._settings.beginGroup(group)
        for kind in ["shipyardicon", "herohrzicon", "squareicon"]:
            presets[kind] = IconPreset.from_config(kind, cls._settings.value(kind, None))
        cls._settings.endGroup()
        return presets

    @classmethod
    def set_presets(cls, group: str, presets: dict[str, IconPreset]):
        cls._settings.beginGroup(group)
        for k, v in presets.items():
            cls._settings.setValue(k, v.__repr__())
        cls._settings.endGroup()


def get_serial() -> tuple[str, int]:
    return Config.get("system", "DeviceAddress"), Config.get("system", "DevicePort")


def get_package() -> str:
    server = Config.get("system", "Server").upper()
    return {"CN": "com.bilibili.azurlane", "JP": "com.YoStarJP.AzurLane", "EN": "com.YoStarEN.AzurLane"}[server]
