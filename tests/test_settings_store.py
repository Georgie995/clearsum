"""Module 2: the app's own settings. Locations only; never secrets."""

import json

import pytest

from clearsum import settings_store as store
from clearsum.settings_store import SettingsError


def test_with_no_settings_file_the_defaults_are_used(tmp_path):
    values = store.load(tmp_path / "settings.json")
    assert values["reports_dir"].endswith("ClearSum Reports")
    assert all(values[k] is None for k in ("ops_hub_path", "ops_hub_config", "ai_triage_path", "ai_triage_python"))


def test_saved_settings_come_back_and_the_file_holds_only_locations(tmp_path, hub):
    path = tmp_path / "app" / "settings.json"
    store.save(path, {"reports_dir": str(tmp_path / "reports"), "ops_hub_path": str(hub[0]),
                      "ops_hub_config": str(hub[1]), "ai_triage_path": "", "ai_triage_python": " "})
    values = store.load(path)
    assert values["ops_hub_path"] == str(hub[0]) and values["ai_triage_path"] is None
    assert sorted(json.loads(path.read_text(encoding="utf-8"))) == sorted(store.FIELDS)


def test_unknown_fields_are_refused_so_a_secret_can_never_be_saved_here(tmp_path):
    with pytest.raises(SettingsError) as error:
        store.validate({"reports_dir": "D:/R", "webhook_secret": "abc"})
    assert error.value.field == "webhook_secret"


@pytest.mark.parametrize("values, field, message", [
    ({"reports_dir": ""}, "reports_dir", "Choose a reports folder"),
    ({"reports_dir": "D:/R", "ops_hub_path": "D:/hub"}, "ops_hub_config", "both"),
    ({"reports_dir": "D:/R", "ai_triage_python": "D:/py.exe"}, "ai_triage_path", "both"),
])
def test_missing_or_half_set_fields_are_named(values, field, message):
    with pytest.raises(SettingsError, match=message) as error:
        store.validate(values)
    assert error.value.field == field


def test_the_delivery_ops_hub_folder_and_settings_file_are_checked(tmp_path, hub):
    wrong_folder = {"reports_dir": "D:/R", "ops_hub_path": str(tmp_path), "ops_hub_config": str(hub[1])}
    with pytest.raises(SettingsError, match="delivery-ops-hub isn't in that folder") as error:
        store.validate(wrong_folder)
    assert error.value.field == "ops_hub_path"
    hub[1].write_text('webhook_url = "http://localhost:5678"\n', encoding="utf-8")
    with pytest.raises(SettingsError, match="reports_dir") as error:
        store.validate({"reports_dir": "D:/R", "ops_hub_path": str(hub[0]), "ops_hub_config": str(hub[1])})
    assert error.value.field == "ops_hub_config"


def test_ai_triage_locations_are_checked(tmp_path, triage):
    with pytest.raises(SettingsError, match="Python") as error:
        store.validate({"reports_dir": "D:/R", "ai_triage_path": str(triage[0]),
                        "ai_triage_python": str(tmp_path / "nope.exe")})
    assert error.value.field == "ai_triage_python"


def test_reports_go_to_delivery_ops_hubs_folder_only_while_alerts_are_set_up(tmp_path, hub):
    values = store.validate({"reports_dir": str(tmp_path / "mine")})
    assert store.reports_folder(values) == str(tmp_path / "mine")
    values = store.validate({"reports_dir": str(tmp_path / "mine"), "ops_hub_path": str(hub[0]),
                             "ops_hub_config": str(hub[1])})
    assert store.reports_folder(values) == str(tmp_path / "hub-reports")


def test_a_damaged_settings_file_is_reported_not_silently_replaced(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(SettingsError, match="can't be read"):
        store.load(path)
    assert path.read_text(encoding="utf-8") == "{ not json"


def test_settings_live_in_the_apps_own_folder_named_after_it():
    assert store.default_settings_file().parent.name == "ClearSum"


# --- The stuck warning's time limit (Georgi: 10 minutes, as in job-watch, changeable here) -----------

def test_the_stuck_warning_time_is_ten_minutes_unless_changed(tmp_path):
    assert store.load(tmp_path / "settings.json")["stall_minutes"] == 10
    assert store.validate({"reports_dir": "D:/R"})["stall_minutes"] == 10                      # older settings files
    assert store.validate({"reports_dir": "D:/R", "stall_minutes": " "})["stall_minutes"] == 10  # box left empty


@pytest.mark.parametrize("given, kept", [("15", 15), (" 1 ", 1), (240, 240), ("240", 240)])
def test_the_stuck_warning_time_takes_whole_minutes_from_1_to_240(given, kept):
    assert store.validate({"reports_dir": "D:/R", "stall_minutes": given})["stall_minutes"] == kept


@pytest.mark.parametrize("given", ["0", "241", "-5", "2.5", "ten", True, 2.5])
def test_any_other_stuck_warning_time_is_refused_in_plain_words(given):
    with pytest.raises(SettingsError, match="whole minutes from 1 to 240") as error:
        store.validate({"reports_dir": "D:/R", "stall_minutes": given})
    assert error.value.field == "stall_minutes"


def test_the_stuck_warning_time_is_saved_and_comes_back(tmp_path):
    path = tmp_path / "settings.json"
    store.save(path, {"reports_dir": str(tmp_path / "r"), "stall_minutes": "25"})
    assert store.load(path)["stall_minutes"] == 25
    assert json.loads(path.read_text(encoding="utf-8"))["stall_minutes"] == 25
