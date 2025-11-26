import os

from PySide6.QtCore import QSettings

from .Data import FaceModeType, IconPresets, parse_icon_preset

settings = QSettings(os.path.expanduser("~/AzurLaneTachieHelper.ini"), QSettings.Format.IniFormat)
default = {
    "system/AdbPath": "3rdparty/adb.exe",
    "system/RecentPath": "",
    "system/Verbose": "false",
    "system/Compression": "original",
    "system/MeshMode": 0,
    "system/FaceMode": "off",
    "system/Serial": "auto",
    "system/Server": "CN",
    "system/Package": "",
}


def init():
    for k, v in default.items():
        if not settings.contains(k):
            settings.setValue(k, v)


def get_config(key: str):
    value = settings.value(key)
    if value == "true":
        return True
    elif value == "false":
        return False
    return value


def set_config(key: str, value):
    settings.setValue(key, value)
    return get_config(key)


def get_presets(group: str) -> IconPresets:
    presets = IconPresets()
    settings.beginGroup(group)
    for k, v in presets.to_dict().items():
        config = settings.value(k)
        if config is not None:
            try:
                data = eval(config)
            except:
                data = parse_icon_preset(config)
            for kk, vv in data.items():
                v[kk] = vv
        settings.setValue(k, v.__repr__())
    settings.endGroup()
    return presets


def set_presets(group: str, presets: IconPresets):
    settings.beginGroup(group)
    for k, v in presets.to_dict().items():
        settings.setValue(k, v.__repr__())
    settings.endGroup()


def get_recent_path() -> str:
    return get_config("system/RecentPath")


def set_recent_path(file: str):
    set_config("system/RecentPath", file)


def get_compression() -> str:
    return get_config("system/Compression")


def get_verbosity() -> bool:
    return get_config("system/Verbose")


def get_face_mode() -> FaceModeType:
    face_mode = get_config("system/FaceMode").lower()
    return {"off": FaceModeType.Off, "auto": FaceModeType.Auto, "custom": FaceModeType.Custom}[face_mode]


def set_face_mode(mode: FaceModeType) -> FaceModeType:
    mode_str = {FaceModeType.Off: "off", FaceModeType.Auto: "auto", FaceModeType.Custom: "custom"}[mode]
    set_config("system/FaceMode", mode_str)


def get_mesh_mode() -> int:
    return int(get_config("system/MeshMode"))


def set_mesh_mode(mode: int) -> int:
    set_config("system/MeshMode", mode)


def get_face_extension(base_name: str, layer_name: str) -> tuple[int, int, int, int]:
    if settings.contains(f"{base_name}/{layer_name}"):
        return eval(get_config(f"{base_name}/{layer_name}"))
    else:
        raise KeyError(f"Face config not found: {base_name}/{layer_name}")


def set_face_extension(base_name: str, layer_name: str, box: tuple[int, int, int, int]):
    set_config(f"{base_name}/{layer_name}", str(box))


def get_adb_path() -> str:
    return get_config("system/AdbPath")


def get_serial() -> str:
    return get_config("system/Serial").lower()


def set_serial(serial: str):
    set_config("system/Serial", serial)


def get_server() -> str:
    return get_config("system/Server").upper()


def set_server(server: str):
    set_config("system/Server", server)


def get_package() -> str:
    package = get_config("system/Package")
    if package == "":
        package = {
            "CN": "com.bilibili.azurlane",
            "JP": "com.YoStarJP.AzurLane",
            "EN": "com.YoStarEN.AzurLane",
        }[get_server()]
    return package
