from PySide6.QtCore import QSettings


class Config:
    def __init__(self, path: str):
        self.settings = QSettings(path, QSettings.Format.IniFormat)

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = {True: "true", False: "false"}[default]
        return eval(str(self.settings.value(key, value)).capitalize())

    def get_str(self, key: str, default: str = "") -> str:
        return self.settings.value(key, default)

    def set(self, key: str, value):
        self.settings.setValue(key, value)
