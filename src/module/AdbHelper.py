import os
import subprocess
from typing import Optional

from ..base import Config
from ..logger import logger
from ..utility import default


class AdbHelper:
    _verbose = False
    _connected = False
    _ports = [5555, 7555, 16384, 59865, 62001]
    _to_pkg = {"CN": "com.bilibili.azurlane", "JP": "com.YoStarJP.AzurLane", "EN": "com.YoStarEN.AzurLane"}

    @classmethod
    def adb(cls, *args):
        adb = Config.get("system", "AdbPath")
        if cls._verbose:
            logger.attr("AdbHelper", " ".join(args))
        return subprocess.check_output([adb, *args]).decode("utf-8")

    @classmethod
    def kill_server(cls):
        cls.adb("kill-server")

    @classmethod
    def start_server(cls):
        cls.adb("start-server")

    @classmethod
    def connect(cls, addr: Optional[str] = None, port: Optional[int] = None):
        cls.kill_server()
        cls.start_server()
        addr = default(addr, Config.get("system", "DeviceAddress"))
        port = default(port, Config.get("system", "DevicePort"))
        if port == "auto":
            port = cls.detect()
        try:
            cls.adb("connect", f"{addr}:{port}")
        except Exception as e:
            logger.error(e)
        else:
            cls._connected = True

    @classmethod
    def devices(cls):
        return cls.adb("devices").split("\r\n")[1:-2]

    @classmethod
    def pull(cls, *files: list[str], target: str = ".", addr: Optional[str] = None, port: Optional[int] = None):
        if not cls._connected:
            cls.connect()
        cls.devices()

        os.makedirs(target, exist_ok=True)
        pkg = cls._to_pkg[Config.get("system", "Server").upper()]
        for file in files:
            folder = os.path.dirname(file)
            if folder != "":
                os.makedirs(os.path.join(target, folder), exist_ok=True)
            path = f"/sdcard/Android/data/{pkg}/files/AssetBundles/{file}"

            addr = default(addr, Config.get("system", "DeviceAddress"))
            port = default(port, Config.get("system", "DevicePort"))

            try:
                cls.adb("-s", f"{addr}:{port}", "pull", path, os.path.join(target, folder))
            except:
                logger.warn(f"Failed on '{file}', maybe in apk")
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
