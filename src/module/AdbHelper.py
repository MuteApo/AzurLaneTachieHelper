import os
import subprocess

from ..base import Config
from ..logger import logger


def get_serial() -> tuple[str, int]:
    return Config.get("system", "DeviceAddress"), Config.get("system", "DevicePort")


def get_package() -> str:
    server = Config.get("system", "Server").upper()
    return {"CN": "com.bilibili.azurlane", "JP": "com.YoStarJP.AzurLane", "EN": "com.YoStarEN.AzurLane"}[server]


class AdbHelper:
    _verbose = False
    _connected = False
    _ports = [5555, 7555, 16384, 59865, 62001]

    @classmethod
    def adb(cls, *args, use_serial: bool = False):
        adb = Config.get("system", "AdbPath")
        if cls._verbose:
            logger.attr("AdbHelper", " ".join(args))
        cmd = [adb]
        if use_serial:
            addr, port = get_serial()
            cmd.extend(["-s", f"{addr}:{port}"])
        cmd.extend(args)
        return subprocess.check_output(cmd).decode("utf-8")

    @classmethod
    def kill_server(cls):
        cls.adb("kill-server")

    @classmethod
    def start_server(cls):
        cls.adb("start-server")

    @classmethod
    def connect(cls):
        addr, port = get_serial()
        if port == "auto":
            port = cls.detect()
        try:
            cls.adb("connect", f"{addr}:{port}")
        except Exception as e:
            logger.error(e)
            cls.kill_server()
            cls.start_server()
        else:
            cls._connected = True

    @classmethod
    def devices(cls):
        return cls.adb("devices").split("\r\n")[1:-2]

    @classmethod
    def pull(cls, *files: list[str], dst_dir: str = ".", use_serial: bool = True):
        if not cls._connected:
            cls.connect()
            logger.info(f"Available devices: {[d.split("\t")[0] for d in cls.devices()]}")
            addr, port = get_serial()
            logger.info(f"Using {f"{addr}:{port}"}")

        os.makedirs(dst_dir, exist_ok=True)
        for file in files:
            folder = os.path.dirname(file)
            if folder != "":
                os.makedirs(os.path.join(dst_dir, folder), exist_ok=True)
            path = f"/sdcard/Android/data/{get_package()}/files/AssetBundles/{file}"

            try:
                cls.adb("pull", path, os.path.join(dst_dir, folder), use_serial=use_serial)
            except:
                logger.warning(f"[bold][[red]Failed[/red]][/bold] '{file}'")
            else:
                logger.info(f"[bold][[green]Succeeded[/green]][/bold] '{file}'")

    @classmethod
    def detect(cls):
        addr, _ = get_serial()
        for port in cls._ports:
            logger.info(f"Detecting emulator port {port}")
            if cls.adb("connect", f"{addr}:{port}").startswith("connected to"):
                return Config.set("system", "DevicePort", port)
        raise Exception(f"Cannot decide emulator port, as not in {cls._ports}")
