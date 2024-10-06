import os
import re
import subprocess

from ..base import Config, get_package, get_serial
from ..logger import logger


class AdbHelper:
    _verbose = False
    _connected = False
    _serials = [
        "127.0.0.1:5555",
        "127.0.0.1:7555",
        "127.0.0.1:16384",
        "127.0.0.1:21503",
        "127.0.0.1:59865",
        "127.0.0.1:62001",
        "emulator-5554",
        "bluestacks4-hyperv",
        "bluestacks5-hyperv",
    ]

    @classmethod
    def adb(cls, *args, use_serial: bool = False) -> str:
        cmd = [Config.get("system", "AdbPath")]
        if use_serial:
            cmd.extend(["-s", get_serial()])
        cmd.extend(args)

        if cls._verbose:
            logger.info(f"[bold][Subprocess][/bold] {" ".join(cmd)}")
        output = subprocess.check_output(cmd).decode("utf-8").strip()
        if cls._verbose:
            logger.info(f"[bold][Subprocess][/bold] {output}")
        return output

    @classmethod
    def kill_server(cls):
        return cls.adb("kill-server")

    @classmethod
    def start_server(cls):
        return cls.adb("start-server")

    @classmethod
    def connect(cls) -> str:
        logger.info(f"[bold][AdbHelper][/bold] Available devices: {", ".join(cls.devices(serial_only=True))}")

        serial = get_serial()
        if serial == "auto":
            serial = cls.detect()

        if re.match(r"^(already )?connected to", cls.adb("connect", serial)):
            cls._connected = True
            return serial

    @classmethod
    def devices(cls, serial_only: bool = False) -> list[str]:
        output = list(map(lambda x: x.split("\t"), cls.adb("devices").split("\r\n")[1:]))
        if serial_only:
            output = list(map(lambda x: x[0], output))
        return output

    @classmethod
    def pull(cls, *files: list[str], dst_dir: str = ".", use_serial: bool = True):
        if not cls._connected:
            logger.info(f"[bold][AdbHelper][/bold] Using {cls.connect()}")

        os.makedirs(dst_dir, exist_ok=True)
        for file in files:
            folder = os.path.dirname(file)
            if folder != "":
                os.makedirs(os.path.join(dst_dir, folder), exist_ok=True)

            try:
                path = f"/sdcard/Android/data/{get_package()}/files/AssetBundles/{file}"
                cls.adb("pull", path, os.path.join(dst_dir, folder), use_serial=use_serial)
            except subprocess.CalledProcessError:
                logger.warning(f"[bold][[red]Failed[/red]][/bold] '{file}'")
            else:
                logger.info(f"[bold][[green]Succeeded[/green]][/bold] '{file}'")

    @classmethod
    def detect(cls):
        logger.info("[bold][AdbHelper][/bold] Auto detecting emulator")

        devices = cls.devices(serial_only=True)
        if devices != []:
            return Config.set("system", "Serial", devices[0])

        for serial in cls._serials:
            if re.match(r"^(already )?connected to", cls.adb("connect", serial)):
                return Config.set("system", "Serial", serial)

        raise ConnectionError(f"Cannot decide emulator, as not in {cls._serials}")
