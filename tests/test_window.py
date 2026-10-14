"""Module 2: the real window, driven automatically (it opens for a few seconds, then closes)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

DRIVER = Path(__file__).with_name("window_driver.py")

pytestmark = pytest.mark.skipif(os.name != "nt", reason="the app is Windows-first; its window test needs Windows")


@pytest.fixture(scope="module")
def shown(tmp_path_factory):
    folder = tmp_path_factory.mktemp("window")
    out = folder / "result.json"
    subprocess.run([sys.executable, str(DRIVER), str(out), str(folder / "settings.json")], timeout=90, check=True)
    return json.loads(out.read_text(encoding="utf-8"))


def test_the_start_screen_opens_with_the_check_button_waiting(shown):
    assert shown["heading"] == "Check a delivery"
    assert shown["check_disabled_at_start"] is True
    assert shown["has_security_policy"] is True


def test_a_file_name_that_looks_like_code_is_shown_as_text_and_does_nothing(shown):
    assert shown["folder_name_shown"].startswith("<img src=x onerror=")
    assert shown["images_in_folder_card"] == 0
    assert shown["title_after_hostile"] == "ClearSum"


def test_the_cards_show_counts_and_plain_errors_and_the_button_wakes_up(shown):
    assert shown["files_text"] == "1,204 files"
    assert shown["manifest_error"] == "a folder, not a manifest"
    assert shown["check_enabled_when_both"] is True


def test_settings_show_status_and_point_at_the_box_that_needs_fixing(shown):
    assert shown["alerts_status"] == "Not set up"
    assert "both" in shown["settings_error"]


def test_a_saved_secret_goes_to_the_safe_and_disappears_from_the_page(shown):
    assert shown["secret_in_store"] is True
    assert shown["secret_box_empty"] is True and shown["secret_saved_shown"] is True
    assert shown["secret_in_page"] is False


def test_the_bundled_fonts_load_from_the_app_itself(shown):
    assert shown["fonts_loaded"] == ["IBM Plex Mono", "Instrument Sans", "Newsreader"]



def test_the_stuck_warning_time_starts_at_10_refuses_0_and_saves_15(shown):
    assert shown["stall_minutes_shown"] == "10"
    assert shown["stall_error"] == "Enter whole minutes from 1 to 240."
    assert shown["stall_error_after_fix"] == "" and shown["stall_minutes_saved"] == 15
