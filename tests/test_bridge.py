"""Module 2: the bridge, the only thing the pages can ask Python to do. Tested without a window."""

import json

import pytest

from delivery_desk_app.bridge import Bridge


@pytest.fixture
def bridge(tmp_path, secrets):
    picks = {}
    b = Bridge(settings_file=tmp_path / "app" / "settings.json", secrets=secrets,
               choose=lambda kind: picks.get(kind))
    b.picks = picks
    return b


def delivery(tmp_path):
    tree = tmp_path / "show-a-ep01"
    for name in ("ShowA/clip_0001.mov", "ShowA/clip_0002.mov", "ShowA/sub/clip_0003.mov"):
        (tree / name).parent.mkdir(parents=True, exist_ok=True)
        (tree / name).write_bytes(b"synthetic")
    manifest = tmp_path / "set1.md5"
    manifest.write_text("# a comment line\n\n" + "".join(f"{'0' * 32}  ShowA/clip_000{i}.mov\n" for i in (1, 2, 3)),
                        encoding="utf-8")
    return tree, manifest


def test_a_folder_is_described_with_its_name_location_and_file_count(tmp_path, bridge):
    tree, _ = delivery(tmp_path)
    assert bridge.describe_folder(str(tree)) == {"ok": True, "name": "show-a-ep01", "path": str(tree), "files": 3}


def test_a_manifest_is_described_with_its_name_and_number_of_entries(tmp_path, bridge):
    _, manifest = delivery(tmp_path)
    assert bridge.describe_manifest(str(manifest)) == {"ok": True, "name": "set1.md5", "path": str(manifest),
                                                      "entries": 3}


def test_dropping_the_wrong_kind_of_thing_gets_a_plain_explanation(tmp_path, bridge):
    tree, manifest = delivery(tmp_path)
    assert "file, not a folder" in bridge.describe_folder(str(manifest))["error"]
    assert "folder, not a manifest file" in bridge.describe_manifest(str(tree))["error"]
    assert "can't be found" in bridge.describe_folder(str(tmp_path / "gone"))["error"]


def test_choose_buttons_use_the_windows_picker_and_cancelling_is_fine(tmp_path, bridge):
    tree, manifest = delivery(tmp_path)
    bridge.picks.update(folder=str(tree), manifest=str(manifest))
    assert bridge.choose_folder()["name"] == "show-a-ep01"
    assert bridge.choose_manifest()["name"] == "set1.md5"
    bridge.picks.clear()
    assert bridge.choose_folder() is None and bridge.choose_manifest() is None


def test_settings_start_from_defaults_and_say_what_is_set_up(bridge):
    view = bridge.get_settings()
    assert view["status"] == {"alerts": "not_set_up", "ai": "not_set_up"}
    assert view["secrets"] == {"webhook_secret": False, "ai_key": False}
    assert view["reports_in_use"] == view["values"]["reports_dir"]


def test_alerts_need_both_the_locations_and_the_webhook_secret(tmp_path, bridge, hub):
    values = {"reports_dir": str(tmp_path / "r"), "ops_hub_path": str(hub[0]), "ops_hub_config": str(hub[1])}
    assert bridge.save_settings(values)["status"]["alerts"] == "needs_secret"
    view = bridge.save_secret("webhook_secret", "hook-123")
    assert view["status"]["alerts"] == "set_up"
    assert view["reports_in_use"] == str(tmp_path / "hub-reports")


def test_ai_summary_works_without_a_key_but_says_so(tmp_path, bridge, triage):
    values = {"reports_dir": str(tmp_path / "r"), "ai_triage_path": str(triage[0]), "ai_triage_python": str(triage[1])}
    assert bridge.save_settings(values)["status"]["ai"] == "no_key"
    assert bridge.save_secret("ai_key", "key-456")["status"]["ai"] == "set_up"


def test_a_settings_mistake_comes_back_naming_the_field_and_nothing_is_saved(tmp_path, bridge):
    result = bridge.save_settings({"reports_dir": str(tmp_path / "r"), "ops_hub_path": "D:/somewhere"})
    assert result["ok"] is False and result["field"] == "ops_hub_config"
    assert not (tmp_path / "app" / "settings.json").exists()


def test_no_secret_value_ever_comes_back_to_the_page(tmp_path, bridge):
    bridge.save_secret("webhook_secret", "hook-SECRET-123")
    bridge.save_secret("ai_key", "key-SECRET-456")
    everything = json.dumps([bridge.get_settings(), bridge.save_settings({"reports_dir": str(tmp_path / "r")}),
                             bridge.remove_secret("ai_key")])
    assert "SECRET" not in everything


def test_secret_mistakes_come_back_as_plain_messages(bridge):
    assert bridge.save_secret("webhook_secret", "   ")["ok"] is False
    assert bridge.save_secret("password", "x")["ok"] is False


def test_the_page_can_only_reach_the_bridges_public_actions():
    public = sorted(name for name in dir(Bridge) if not name.startswith("_"))
    assert public == ["choose_folder", "choose_manifest", "choose_path", "describe_folder", "describe_manifest",
                      "get_settings", "remove_secret", "save_secret", "save_settings"]
