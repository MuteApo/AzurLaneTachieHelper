from pathlib import Path

from PIL import Image
from PySide6.QtCore import QSettings

from adapters.documents import Preferences, PresetDocument, ProjectDefaultsDocument
from adapters.legacy import apply_legacy, preview_legacy
from adapters.storage import Settings
from application.session import Session
from domain.model import Asset, FaceMode, Kind, ObjectRef, Placement, Project


def write_ini(path: Path, values: dict[str, object]) -> None:
    settings = QSettings(str(path), QSettings.Format.IniFormat)
    for key, value in values.items():
        settings.setValue(key, value)
    settings.sync()


def test_legacy_preview_and_merge_preserve_source_and_unrelated_settings(tmp_path):
    source = tmp_path / "legacy.ini"
    repository = tmp_path / "old-workspace"
    write_ini(
        source,
        {
            "system/AdbPath": "3rdparty/adb.exe",
            "system/RecentPath": "projects/ship/ship",
            "system/Server": "jp",
            "system/FaceMode": "custom",
            "system/MeshMode": "1",
            "system/Verbose": "true",
            "ship/shipyardicon": "{'pivot': (0.4, 0.7), 'scale': 0.8, 'angle': 15}",
            "ship/herohrzicon": "IconPreset(size=(360, 80), pivot=(0.2, 0.6), scale=0.9, angle=-10)",
            "ship/squareicon": "<IconPreset pivot=(0.5, 0.6), scale=0.75 angle=0>",
            "ship/paintingface": "[-10, 0, 20, 30]",
            "ship/body": "(1, 2, 3, 4)",
        },
    )
    original_bytes = source.read_bytes()
    settings = Settings(tmp_path / "preferences.json")
    settings.update(
        {
            "language": "en",
            "project_defaults": {
                "other": ProjectDefaultsDocument(extensions={"body": (0, 0, 1, 1)}),
                "ship": ProjectDefaultsDocument(extensions={"decoration": (1, 0, 0, 0)}),
            },
        }
    )
    previous = settings.path.read_bytes()
    preview = preview_legacy(source, repository)
    assert settings.path.read_bytes() == previous
    assert not preview.issues
    assert preview.preset_count == 3 and preview.extension_count == 2
    assert preview.ignored == ["system/MeshMode", "system/Verbose"]
    assert preview.preferences["adb_path"] == str(repository / "3rdparty" / "adb.exe")
    assert preview.preferences["recent_projects"] == [str(repository / "projects" / "ship" / "ship")]
    apply_legacy(preview, settings)
    restored = Settings(settings.path).data
    assert restored.language == "en"
    assert restored.server == "JP" and restored.face_mode == FaceMode.CUSTOM
    assert "mesh_mode" not in preview.preferences
    assert restored.project_defaults["ship"].extensions["decoration"] == (1, 0, 0, 0)
    assert restored.project_defaults["ship"].presets["squareicon"].scale == 0.75
    assert "other" in restored.project_defaults
    assert source.read_bytes() == original_bytes


def test_invalid_and_executable_legacy_values_are_reported_not_executed(tmp_path):
    source = tmp_path / "legacy.ini"
    marker = tmp_path / "must-not-exist"
    write_ini(
        source,
        {
            "system/MeshMode": "7",
            "ship/shipyardicon": f"__import__('pathlib').Path({str(marker)!r}).write_text('executed')",
            "ship/squareicon": "{'scale': -1}",
            "ship/body": "(1, 2, 3)",
            "ship/paintingface": "(0, 0, 10, 10)",
        },
    )
    preview = preview_legacy(source, tmp_path)
    assert {issue.key for issue in preview.issues} == {
        "ship/shipyardicon",
        "ship/squareicon",
        "ship/body",
    }
    assert preview.preset_count == 0 and preview.extension_count == 1
    assert preview.ignored == ["system/MeshMode"]
    assert not marker.exists()
    settings = Settings(tmp_path / "next.json")
    apply_legacy(preview, settings)
    assert settings.data.project_defaults["ship"].extensions == {"paintingface": (0, 0, 10, 10)}


def test_defaults_apply_to_metadata_but_saved_document_takes_precedence(tmp_path, monkeypatch):
    metadata = tmp_path / "ship_n"
    metadata.write_bytes(b"mock Unity metadata")

    def load(self, path, manifest, progress):
        return Project(
            path,
            "ship_n",
            (8, 8),
            (0, 0),
            [
                Asset(
                    "body",
                    "body",
                    Kind.PAINTING,
                    ObjectRef(metadata, "cabinet", 1),
                    Image.new("RGBA", (8, 8)),
                    Placement((0, 0), (8, 8)),
                ),
            ],
        )

    monkeypatch.setattr("application.session.UnityReader.load", load)
    monkeypatch.setattr("application.session.discover_manifest", lambda path: None)
    defaults = Preferences(
        face_mode=FaceMode.CUSTOM,
        project_defaults={
            "ship": ProjectDefaultsDocument(
                presets={"squareicon": PresetDocument(size=(116, 116), scale=0.9)},
                extensions={"body": (1, 2, 3, 4)},
            ),
        },
    )
    session = Session.open(metadata, defaults=defaults)
    assert session.project.options.face_mode == FaceMode.CUSTOM
    assert session.project.options.extensions == {"body": (1, 2, 3, 4)}
    assert session.presets["squareicon"].scale == 0.9
    assert not session.dirty
    session.set_options(face_mode=FaceMode.OFF)
    saved = session.save(tmp_path / "ship.tachie.json")
    defaults.project_defaults["ship"].presets["squareicon"].scale = 0.2
    reopened = Session.open(saved, defaults=defaults)
    assert reopened.project.options.face_mode == FaceMode.OFF
    assert reopened.presets["squareicon"].scale == 0.9
    session.close()
    reopened.close()
