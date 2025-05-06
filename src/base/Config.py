from PySide6.QtCore import QSettings

from .Data import FaceModeType, IconPreset

settings = QSettings("./config.ini", QSettings.Format.IniFormat)
default = {
    "system/RecentPath": "",
    "system/Compression": "original",
    "system/Verbose": "false",
    "system/FaceMode": "off",
    "system/AdbPath": "3rdparty/adb.exe",
    "system/Serial": "auto",
    "system/Server": "CN",
}


def init():
    for k, v in default.items():
        if not settings.contains(k):
            settings.setValue(k, v)


def get_config(group: str, key: str):
    value = settings.value(f"{group}/{key}")
    if value == "true":
        return True
    elif value == "false":
        return False
    return value


def set_config(group: str, key: str, value):
    settings.setValue(f"{group}/{key}", value)
    return get_config(group, key)


def get_presets(group: str) -> dict[str, IconPreset]:
    presets = {}
    settings.beginGroup(group)
    for kind in ["shipyardicon", "herohrzicon", "squareicon"]:
        presets[kind] = IconPreset.from_config(kind, settings.value(kind, None))
    settings.endGroup()
    return presets


def set_presets(group: str, presets: dict[str, IconPreset]):
    settings.beginGroup(group)
    for k, v in presets.items():
        settings.setValue(k, v.__repr__())
    settings.endGroup()


def get_recent_path() -> str:
    return get_config("system", "RecentPath")


def set_recent_path(file: str):
    set_config("system", "RecentPath", file)


def get_compression() -> str:
    return get_config("system", "Compression")


def get_verbosity() -> bool:
    return get_config("system", "Verbose")


def get_face_mode() -> FaceModeType:
    face_mode = get_config("system", "FaceMode").lower()
    return {"off": FaceModeType.Off, "adaptive": FaceModeType.Adaptive, "maximum": FaceModeType.Maximum}[face_mode]


def set_face_mode(mode: FaceModeType) -> FaceModeType:
    mode_str = {FaceModeType.Off: "off", FaceModeType.Adaptive: "adaptive", FaceModeType.Maximum: "maximum"}[mode]
    set_config("system", "FaceMode", mode_str)


def get_adb_path() -> str:
    return get_config("system", "AdbPath")


def get_serial() -> str:
    return get_config("system", "Serial").lower()


def set_serial(serial: str):
    set_config("system", "Serial", serial)


def get_server() -> str:
    return get_config("system", "Server").upper()


def set_server(server: str):
    set_config("system", "Server", server)


def get_package() -> str:
    return {
        "CN": "com.bilibili.azurlane",
        "JP": "com.YoStarJP.AzurLane",
        "EN": "com.YoStarEN.AzurLane",
    }[get_server()]
