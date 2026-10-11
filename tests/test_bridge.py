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
    assert public == ["check_status", "choose_folder", "choose_manifest", "choose_path", "copy_email",
                      "describe_folder", "describe_manifest", "get_note", "get_result", "get_settings",
                      "list_checks", "make_email", "open_email", "remove_secret", "save_answer", "save_secret",
                      "save_settings", "show_report_folder", "start_check", "stop_check"]


# --- Module 3: starting a check, its results, and Show report in folder ---------------------------------

import threading
from pathlib import Path
from types import SimpleNamespace


class FakeEngine:
    """Stands in for delivery-desk's engine: records what it was asked, writes a tiny report."""
    def __init__(self, reports):
        self.calls = []
        self.reports = Path(reports)

    def check(self, settings, tree, doctor_args, secrets=None, output=None, stop=None):
        self.calls.append({"settings": settings, "tree": tree, "args": doctor_args, "secrets": secrets})
        folder = self.reports / "report-2026-10-11_160742"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "report.json").write_text(json.dumps({
            "header": {"result": "CLEAN", "tree": str(tree), "run_at": "2026-10-11T16:07:42+01:00",
                       "counts": {"ERROR": 0, "WARNING": 0, "INFO": 0}, "manifests": [{"path": "set1.md5", "entries": 3}]},
            "causes": [], "findings": []}), encoding="utf-8")
        return SimpleNamespace(code=0, result="CLEAN", report_folder=folder, note=None, stopped=False)


@pytest.fixture
def checker(tmp_path, secrets):
    reports = tmp_path / "reports"
    engine = FakeEngine(reports)
    opened = []
    b = Bridge(settings_file=tmp_path / "app" / "settings.json", secrets=secrets, engine=engine, opener=opened.append)
    b.save_settings({"reports_dir": str(reports)})
    b.engine, b.opened, b.reports = engine, opened, reports
    return b


def wait_done(bridge, timeout=5):
    import time
    end = time.monotonic() + timeout
    while bridge.check_status()["state"] in ("running", "idle"):
        assert time.monotonic() < end
        time.sleep(0.02)
    return bridge.check_status()


def test_without_alerts_the_check_runs_manifest_doctor_directly_with_a_progress_file(tmp_path, checker):
    tree, manifest = delivery(tmp_path)
    assert checker.start_check(str(tree), str(manifest)) == {"ok": True}
    assert wait_done(checker)["state"] == "finished"
    [call] = checker.engine.calls
    assert call["settings"]["ops_hub_path"] is None and call["settings"]["reports_dir"] == str(checker.reports)
    assert Path(call["settings"]["manifest_doctor_path"]).name == "delivery-verify"
    args = call["args"]
    assert args[:2] == ["--manifest", str(manifest)] and args[2] == "--progress-file"
    assert not Path(args[3]).resolve().is_relative_to(tree.resolve())     # never inside the delivery


def test_with_alerts_the_check_goes_through_delivery_ops_hub_with_the_saved_secrets(tmp_path, checker, hub):
    checker.save_settings({"reports_dir": str(checker.reports), "ops_hub_path": str(hub[0]), "ops_hub_config": str(hub[1])})
    checker.save_secret("webhook_secret", "hook-123")
    tree, manifest = delivery(tmp_path)
    checker.start_check(str(tree), str(manifest))
    wait_done(checker)
    [call] = checker.engine.calls
    assert call["settings"]["ops_hub_path"] == str(hub[0])
    assert call["settings"]["reports_dir"] == str(tmp_path / "hub-reports")
    assert call["secrets"] == {"OPS_HUB_WEBHOOK_SECRET": "hook-123"}


def test_only_one_check_runs_at_a_time(tmp_path, checker):
    tree, manifest = delivery(tmp_path)
    gate = threading.Event()
    original = checker.engine.check
    checker.engine.check = lambda *a, **k: (gate.wait(5), original(*a, **k))[1]
    assert checker.start_check(str(tree), str(manifest))["ok"] is True
    second = checker.start_check(str(tree), str(manifest))
    assert second["ok"] is False and "already running" in second["error"]
    gate.set()
    wait_done(checker)


def test_a_check_wont_start_without_a_real_folder_and_manifest(tmp_path, checker):
    tree, manifest = delivery(tmp_path)
    assert "not a folder" in checker.start_check(str(manifest), str(manifest))["error"]
    assert "not a manifest" in checker.start_check(str(tree), str(tree))["error"]


def test_results_are_read_only_from_report_folders_inside_the_reports_folder(tmp_path, checker):
    tree, manifest = delivery(tmp_path)
    checker.start_check(str(tree), str(manifest))
    report_id = wait_done(checker)["outcome"]["report_id"]
    assert checker.get_result(report_id)["headline"] == "All 3 files match the manifest."
    for sneaky in ("..", "../app", r"C:\Windows", "report-x/../../app", r"report-x\..\..\app", "", None, 42):
        assert checker.get_result(sneaky)["ok"] is False


def test_show_report_in_folder_opens_only_a_real_report_folder(tmp_path, checker):
    tree, manifest = delivery(tmp_path)
    checker.start_check(str(tree), str(manifest))
    report_id = wait_done(checker)["outcome"]["report_id"]
    assert checker.show_report_folder(report_id) == {"ok": True}
    assert checker.opened == [checker.reports / report_id]
    assert checker.show_report_folder(r"..\..\Windows")["ok"] is False
    assert len(checker.opened) == 1


def test_the_status_says_whether_alerts_were_on_for_this_check(tmp_path, checker, hub):
    tree, manifest = delivery(tmp_path)
    checker.start_check(str(tree), str(manifest))
    assert wait_done(checker)["alerts"] is False
    checker.save_settings({"reports_dir": str(checker.reports), "ops_hub_path": str(hub[0]), "ops_hub_config": str(hub[1])})
    checker.start_check(str(tree), str(manifest))
    assert wait_done(checker)["alerts"] is True
