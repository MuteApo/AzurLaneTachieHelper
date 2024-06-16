import os
import subprocess
from typing import Optional

from ..base import Config
from ..logger import logger


def exists(v):
    return v is not None


def default(v, d):
    return v if exists(v) else d


class AdbHelper:
    _ports = [5555, 7555, 16384, 59865, 62001]
    _to_pkg = {"CN": "com.bilibili.azurlane", "JP": "com.YoStarJP.AzurLane", "EN": "com.YoStarEN.AzurLane"}

    @classmethod
    def adb(cls, *args):
        adb = Config.get("system", "AdbPath")
        return subprocess.check_output([adb, *args]).decode("utf-8")

    @classmethod
    def kill_server(cls):
        cls.adb("kill-server")

    @classmethod
    def start_server(cls):
        cls.adb("start-server")

    @classmethod
    def connect(cls, addr: Optional[str] = None, port: Optional[int] = None):
        logger.info("Initializing adb")
        cls.kill_server()
        cls.start_server()
        addr = default(addr, Config.get("system", "DeviceAddress"))
        port = default(port, Config.get("system", "DevicePort"))
        if port == "auto":
            port = cls.detect()
        cls.adb("connect", f"{addr}:{port}")

    @classmethod
    def devices(cls):
        return cls.adb("devices").split("\r\n")[1:-2]

    @classmethod
    def pull(cls, *files: list[str], target: str = "."):
        os.makedirs(target, exist_ok=True)
        pkg = cls._to_pkg[Config.get("system", "Server").upper()]
        for file in files:
            folder = os.path.dirname(file)
            if folder != "":
                os.makedirs(os.path.join(target, folder), exist_ok=True)
            path = f"/sdcard/Android/data/{pkg}/files/AssetBundles/{file}"

            try:
                cls.adb("pull", path, os.path.join(target, folder))
            except:
                logger.warn(f'Failed on pulling \'{file}\', maybe in apk')
            else:
                logger.info(f"Pulled '{path}'")

    @classmethod
    def detect(cls):
        logger.info("Detecting emulator port")
        addr = Config.get("system", "DeviceAddress")
        for port in cls._ports:
            logger.info(f"Trying port {port}")
            if cls.adb("connect", f"{addr}:{port}").startswith("connected to"):
                Config.set("system", "DevicePort", port)
                return port
        raise Exception(f"Cannot decide emulator port, as not in {cls._ports}")
