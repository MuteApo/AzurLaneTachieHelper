from PySide6.QtCore import QSettings

from .Data import IconPreset
from .Vector import Vector2


class Config:
    def __init__(self, path: str):
        self.settings = QSettings(path, QSettings.Format.IniFormat)

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = {True: "true", False: "false"}[default]
        return eval(str(self.settings.value(key, value)).capitalize())

    def get_str(self, key: str, default: str = "") -> str:
        return self.settings.value(key, default)

    def get_vec2(self, key: str, default: Vector2 = Vector2(0, 0)) -> Vector2:
        return self.settings.value(key, default)

    def set(self, key: str, value):
        self.settings.setValue(key, value)

    def get_presets(self, prefix: str) -> dict[str, IconPreset]:
        self.settings.beginGroup(prefix)
        presets = IconPreset.defaults()
        for k, v in presets.items():
            v.from_repr(self.settings.value(k, presets[k].__repr__()))
        self.settings.endGroup()
        return presets

    def set_presets(self, prefix: str, presets: dict[str, IconPreset]):
        self.settings.beginGroup(prefix)
        for k, v in presets.items():
            self.settings.setValue(k, v.__repr__())
        self.settings.endGroup()
