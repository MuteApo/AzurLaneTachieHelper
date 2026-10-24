import os
from pathlib import Path
from subprocess import CompletedProcess
from types import SimpleNamespace
from unittest.mock import Mock
from zipfile import ZipFile

import pytest
from adbutils.errors import AdbError, AdbTimeout

from adapters.adb import PACKAGES, AdbClient


@pytest.fixture
def server(monkeypatch):
    server = Mock()
    server.host, server.port = "127.0.0.1", 5037
    server.list.return_value = [SimpleNamespace(serial="usb", state="device")]
    server.device.return_value.sync.pull_file.side_effect = lambda remote, local: Path(local).write_bytes(
        b"bundle"
    )
    monkeypatch.setattr("adapters.adb.adbutils.AdbClient", lambda **kwargs: server)
    return server


def test_explicit_device_never_falls_back_to_another(server):
    with pytest.raises(RuntimeError, match="missing-usb"):
        AdbClient(serial="missing-usb").connect()
    server.connect.assert_not_called()
    server.device.assert_not_called()


def test_auto_devices_filter_offline_and_use_first_online_device(server):
    server.list.return_value = [
        SimpleNamespace(serial=serial, state=state)
        for serial, state in [("a", "device"), ("b", "offline"), ("c", "unauthorized"), ("d", "device")]
    ]
    client = AdbClient()
    assert client.devices() == ["a", "d"]
    assert client.connect() == "a"


def test_auto_connect_tries_emulator_after_timeout(server):
    server.list.side_effect = [[], [SimpleNamespace(serial="127.0.0.1:7555", state="device")]]
    server.connect.side_effect = [AdbTimeout("timeout"), "connected"]
    assert AdbClient().connect() == "127.0.0.1:7555"
    assert server.connect.call_args_list[0].args == ("127.0.0.1:5555",)
    assert server.connect.call_args_list[1].args == ("127.0.0.1:7555",)


def test_failed_explicit_tcp_connection_does_not_select_other_device(server):
    server.connect.return_value = "unable to connect"
    with pytest.raises(RuntimeError, match="127.0.0.1:5555"):
        AdbClient(serial="127.0.0.1:5555").connect()
    server.connect.assert_called_once_with("127.0.0.1:5555", timeout=15)
    server.device.assert_not_called()


def test_custom_binary_only_starts_server_lazily_without_changing_environment(server, monkeypatch):
    run = Mock(return_value=CompletedProcess([], 0, "", ""))
    monkeypatch.setattr("adapters.adb.subprocess.run", run)
    before = os.environ.get("ADBUTILS_ADB_PATH")
    client = AdbClient(executable="custom/adb.exe")
    run.assert_not_called()
    server.list.assert_not_called()
    assert client.connect() == "usb"
    client.devices()
    run.assert_called_once()
    assert run.call_args.args[0] == ["custom/adb.exe", "-H", "127.0.0.1", "-P", "5037", "start-server"]
    assert os.environ.get("ADBUTILS_ADB_PATH") == before


def test_startup_and_server_errors_are_reported(server, monkeypatch):
    monkeypatch.setattr(
        "adapters.adb.subprocess.run", lambda *args, **kwargs: CompletedProcess([], 1, "", "cannot start")
    )
    with pytest.raises(RuntimeError, match="cannot start"):
        AdbClient(executable="custom/adb.exe").devices()
    server.list.assert_not_called()
    server.list.side_effect = AdbError("server unavailable")
    with pytest.raises(RuntimeError, match="server unavailable"):
        AdbClient().devices()


def test_project_pulls_nested_dependencies_and_apk_icon_fallback(server, tmp_path):
    device = server.device.return_value
    device.shell2.return_value = SimpleNamespace(
        returncode=0, output="package:/data/app/base.apk\npackage:/data/app/split.apk"
    )

    def pull(remote, local):
        if remote.endswith("base.apk"):
            with ZipFile(local, "w") as archive:
                archive.writestr("assets/AssetBundles/squareicon/ship.ys", b"icon")
                archive.writestr("../../unwanted", b"do not extract")
        elif remote.endswith("split.apk"):
            with ZipFile(local, "w") as archive:
                archive.writestr("assets/AssetBundles/paintingface/ship", b"face")
        elif "/squareicon/" in remote or "/paintingface/" in remote:
            local.write_bytes(b"partial transfer")
            raise AdbError("remote object does not exist")
        else:
            local.write_bytes(b"bundle")

    device.sync.pull_file.side_effect = pull
    client = AdbClient(package=PACKAGES["JP"])
    index = {
        "painting/ship": ("painting/ship_tex",),
        "painting/ship_tex": ("shared/common",),
        "painting/ship_n": ("shared/common",),
    }
    destination = tmp_path / "project"
    result = client.pull_project("ship", index, destination)
    assert result.metadata == destination / "ship"
    assert (destination / "ship_n").read_bytes() == b"bundle"
    assert (destination / "squareicon/ship").read_bytes() == b"icon"
    assert (destination / "paintingface/ship").read_bytes() == b"face"
    assert result.failed == []
    assert len(result.files) == 8
    calls = device.sync.pull_file.call_args_list
    assert len([call for call in calls if call.args[0].endswith("/shared/common")]) == 1
    assert not (tmp_path / "unwanted").exists()
    assert all(call.kwargs == {"serial": "usb"} for call in server.device.call_args_list)
    device.shell2.assert_called_once_with(["pm", "path", PACKAGES["JP"]], timeout=30)


def test_failed_transfer_is_not_published_and_apk_fallback_can_be_disabled(server, tmp_path):
    def fail(remote, local):
        local.write_bytes(b"partial")
        raise AdbTimeout("transfer stalled")

    device = server.device.return_value
    device.sync.pull_file.side_effect = fail
    result = AdbClient(apk_fallback=False).pull_project("ship", {"painting/ship": []}, tmp_path)
    assert result.metadata is None and not result.files
    assert result.failed
    assert list(tmp_path.iterdir()) == []
    device.shell2.assert_not_called()


def test_failed_apk_query_preserves_missing_results(server, tmp_path, caplog):
    device = server.device.return_value
    device.sync.pull_file.side_effect = AdbError("not found")
    device.shell2.return_value = SimpleNamespace(returncode=1, output="package manager unavailable")
    result = AdbClient().pull_project("ship", {"painting/ship": []}, tmp_path)
    assert result.failed and not result.files
    assert "package manager unavailable" in caplog.text
    assert all(not call.args[0].endswith(".apk") for call in device.sync.pull_file.call_args_list)


def test_output_and_manifest_paths_are_checked_before_device_access(server, tmp_path):
    client = AdbClient()
    with pytest.raises(ValueError, match="resource path"):
        client.pull_project("ship", {"painting/ship": ["../outside"]}, tmp_path)
    (tmp_path / "ship").write_bytes(b"original")
    with pytest.raises(FileExistsError):
        client.pull_project("ship", {"painting/ship": []}, tmp_path)
    assert (tmp_path / "ship").read_bytes() == b"original"
    server.list.assert_not_called()


def test_progress_cancellation_propagates_without_publishing(server, tmp_path):
    def cancel(*args):
        raise InterruptedError("cancelled")

    with pytest.raises(InterruptedError):
        AdbClient().pull_project("ship", {"painting/ship": []}, tmp_path, cancel)
    assert list(tmp_path.iterdir()) == []
    server.device.return_value.sync.pull_file.assert_not_called()
