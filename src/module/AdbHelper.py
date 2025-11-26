import os
import re
import subprocess

from ..base import Config
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
    def adb(cls, *args: str, progress: bool = False) -> str:
        cmd = [Config.get_adb_path(), "-s", Config.get_serial(), *args]

        stderr = None if progress else subprocess.DEVNULL
        if Config.get_verbosity():
            logger.attr("[Subprocess]", " ".join(cmd))
            output = subprocess.check_output(cmd, stderr=stderr).decode("utf-8").strip()
            logger.attr("[Subprocess]", output)
        else:
            output = subprocess.check_output(cmd, stderr=stderr).decode("utf-8").strip()

        return output

    @classmethod
    def exec_out(cls, *args: str, as_root: bool = False) -> str:
        cmd = ["exec-out"]
        if as_root:
            cmd.extend(["su", "-c"])
        cmd.append(" ".join(args))

        return cls.adb(*cmd)

    @classmethod
    def kill_server(cls):
        return cls.adb("kill-server")

    @classmethod
    def start_server(cls):
        return cls.adb("start-server")

    @classmethod
    def connect(cls) -> str:
        devices = cls.devices(serial_only=True)
        assert devices, "No device found, please check emulator status or adb connection"
        logger.attr("AdbHelper", f"Available devices: {", ".join(devices)}")

        serial = Config.get_serial()
        if serial == "auto":
            serial = cls.detect()

        if serial not in devices:
            serial = devices[0]

        Config.set_serial(serial)
        cls.adb("connect", serial)
        cls._connected = True

        return serial

    @classmethod
    def devices(cls, serial_only: bool = False) -> list[str]:
        output = list(map(lambda x: x.split("\t"), cls.adb("devices").split("\r\n")[1:]))
        if serial_only:
            output = list(map(lambda x: x[0], output))
        return output

    @classmethod
    def pull(
        cls, *files: str, dst_dir: str = ".", add_prefix: bool = False, progress: bool = False, log: bool = True
    ) -> tuple[list[str], list[str]]:
        os.makedirs(dst_dir, exist_ok=True)

        if not cls._connected:
            logger.attr("AdbHelper", f"Connected to {cls.connect()}")

        succeeded, failed = [], []
        for file in files:
            if add_prefix:
                path = f"/sdcard/Android/data/{Config.get_package()}/files/AssetBundles/{file}"
                folder = f"{dst_dir}/{os.path.dirname(file)}"
                os.makedirs(folder, exist_ok=True)
            else:
                path = file
                folder = dst_dir

            try:
                cls.adb("pull", path, folder, progress=progress)
            except subprocess.CalledProcessError:
                failed.append(file)
                if log:
                    logger.attr("[red]Failed[/red]", file)
            else:
                succeeded.append(file)
                if log:
                    logger.attr("[green]Succeeded[/green]", file)

        return succeeded, failed

    @classmethod
    def detect(cls):
        logger.attr("AdbHelper", "Auto detecting emulator")

        devices = cls.devices(serial_only=True)
        if devices != []:
            return Config.set_serial(devices[0])

        for serial in cls._serials:
            if re.match(r"^(already )?connected to", cls.adb("connect", serial)):
                return Config.set_serial(serial)

        raise ConnectionError(f"Cannot decide emulator, as not in {cls._serials}")
