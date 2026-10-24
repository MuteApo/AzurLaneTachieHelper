"""Resource selection recognizes supported folder layouts without opening Unity files."""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog

from ui.dialogs.resource_open import OpenResourceDialog, choose_resource, discover_resources


def file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"not decoded during selection")
    return path


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_discovers_saved_legacy_and_painting_layouts_one_level(tmp_path):
    saved = file(tmp_path / "my-edits.tachie.json")
    legacy = file(tmp_path / "ship_a" / "ship_a")
    normal = file(tmp_path / "ship_a" / "ship_a_n")
    pulled = file(tmp_path / "ship_b" / "painting" / "ship_b")
    renamed = file(tmp_path / "working-copy" / "ship_c")
    renamed_normal = file(tmp_path / "working-copy" / "ship_c_n")
    file(tmp_path / "ship_b" / "painting" / "ship_b_tex")
    file(tmp_path / "ship_b" / "painting" / "ship_b_tex2")
    file(tmp_path / "ship_b" / "painting" / "shared_atlas")
    file(tmp_path / "ship_a" / "custom_builtin")
    file(tmp_path / "ship_a" / "dependencies")
    file(tmp_path / "ship_a" / "unknown_dependency")
    file(tmp_path / "ship_a" / "shipyardicon" / "ship_a")
    file(tmp_path / "unrelated" / "deep" / "deep")
    assert set(discover_resources(tmp_path)) == {saved, legacy, normal, pulled, renamed, renamed_normal}
    assert discover_resources(tmp_path)[0] == saved
    assert discover_resources(tmp_path / "ship_b" / "painting") == [pulled]
    assert discover_resources(tmp_path / "ship_a" / "shipyardicon") == []


def test_single_candidate_opens_without_an_extra_choice(app, tmp_path, monkeypatch):
    project = tmp_path / "ship"
    expected = file(project / "ship")
    monkeypatch.setattr(
        OpenResourceDialog, "exec", lambda self: pytest.fail("single candidate needs no chooser")
    )
    assert choose_resource(folder=project) == expected


def test_multiple_candidates_require_choice_and_cancel_returns_none(app, tmp_path, monkeypatch):
    first = file(tmp_path / "one" / "one")
    second = file(tmp_path / "two" / "two")
    dialog = OpenResourceDialog(folder=tmp_path)
    assert dialog.selected_path is None
    assert not dialog.open_button.isEnabled()
    item = next(
        dialog.list.topLevelItem(i)
        for i in range(dialog.list.topLevelItemCount())
        if dialog.list.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole) == second
    )
    dialog.list.setCurrentItem(item)
    dialog.accept()
    assert dialog.selected_path == second
    assert dialog.result() == QDialog.DialogCode.Accepted
    monkeypatch.setattr(OpenResourceDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    assert choose_resource(folder=tmp_path) is None
    assert first.exists() and second.exists()


def test_empty_folder_keeps_explicit_file_fallback(app, tmp_path, monkeypatch):
    file(tmp_path / "custom_builtin")
    file(tmp_path / "dependencies")
    metadata = file(tmp_path / "manual-resource")
    dialog = OpenResourceDialog(folder=tmp_path)
    assert dialog.candidates == []
    assert not dialog.open_button.isEnabled()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(metadata), ""))
    dialog.choose_file()
    assert dialog.selected_path == metadata
    assert dialog.result() == QDialog.DialogCode.Accepted
