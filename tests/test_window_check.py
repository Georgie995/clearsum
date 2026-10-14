"""Module 3: real checks in the real window (it opens for about half a minute, then closes).
Needs delivery-desk and manifest-doctor next to the app. No alerts, no AI, no network."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from clearsum import paths

DRIVER = Path(__file__).with_name("check_driver.py")

pytestmark = [
    pytest.mark.skipif(os.name != "nt", reason="the app is Windows-first; its window test needs Windows"),
    pytest.mark.skipif(not (paths.DELIVERY_DESK / "delivery_desk").is_dir()
                       or not (paths.MANIFEST_DOCTOR / "manifest_doctor").is_dir(),
                       reason="delivery-desk and manifest-doctor must sit next to the app"),
]


@pytest.fixture(scope="module")
def shown(tmp_path_factory):
    folder = tmp_path_factory.mktemp("checks")
    out = folder / "result.json"
    subprocess.run([sys.executable, str(DRIVER), str(out), str(folder)], timeout=240, check=True)
    return json.loads(out.read_text(encoding="utf-8"))


def test_a_delivery_with_a_file_listed_twice_shows_problems_in_plain_words(shown):
    assert shown["problems_screen"] is True
    assert shown["pill"] == "PROBLEMS FOUND"
    assert shown["headline"] == "2 files didn't arrive as expected."    # the duplicate, and the missing one
    assert shown["errors"] == "3"
    assert shown["cause_titles"] == ["A file is listed twice in the manifest, with different checksums"]
    assert shown["cause_files"] == ["ShowA/Reel01/clip_0004.mov"]
    assert shown["rows"] == 3


def test_a_file_name_that_looks_like_code_is_just_text_on_the_results_screen(shown):
    assert len(shown["hostile_row_text"]) == 1 and shown["hostile_row_text"][0].startswith("ShowA/<img src=x")
    assert shown["images_in_results"] == 0
    assert shown["title_after_results"] == "ClearSum"


def test_the_problems_screen_offers_the_note_and_shows_what_the_tools_said(shown):
    assert shown["start_note_shown"] is True          # a working note was written for PROBLEMS FOUND
    assert shown["alert_line_hidden"] is True         # alerts aren't set up in this test
    assert "PROBLEMS FOUND" in shown["tools_said"] and "Working note written" in shown["tools_said"]


def test_the_findings_filter_says_when_a_group_is_empty(shown):
    assert shown["info_rows"] == 0 and shown["empty_note_shown"] is True


def test_check_another_starts_fresh_and_a_clean_delivery_is_all_clear(shown):
    assert shown["back_to_start_empty"] is True
    assert shown["allclear_screen"] is True
    assert shown["allclear_headline"] == "All 4 files match the manifest."
    assert set(shown["checked_values"]) == {"None"}


def test_a_delivery_that_cant_be_checked_says_so_with_the_tools_own_words(shown):
    assert shown["notchecked_screen"] is True
    assert "stopped before it could verify anything" in shown["nc_reason"]
    assert "is empty" in shown["nc_output"]


def test_reports_were_written_and_no_progress_files_were_left_behind(shown):
    assert len(shown["reports"]) == 2                 # the problem check and the clean check
    assert shown["leftover_progress_files"] == []


def test_earlier_checks_lists_both_reports_newest_first_with_note_progress(shown):
    rows = shown["earlier_rows"]
    assert [row[1] for row in rows][:2] == ["show-a-ep02", "show-a-ep01"]
    assert [row[3] for row in rows][:2] == ["All clear", "Problems found"]
    assert [row[4] for row in rows][:2] == ["No note needed", "Not started"]
    assert [row[0] for row in rows] == ["today", "today", "1 Jan 2000"]


def test_the_recent_list_shows_the_latest_checks(shown):
    assert len(shown["recent"]) == 3
    assert shown["recent"][0].startswith("show-a-ep02") and "All clear" in shown["recent"][0]


def test_a_delivery_name_that_looks_like_code_is_just_text_in_the_lists(shown):
    assert shown["earlier_rows"][2][1].startswith("<img src=x onerror=")
    assert shown["images_in_earlier_or_recent"] == 0
    assert shown["title_after_earlier"] == "ClearSum"


def test_searching_and_reopening_an_earlier_check(shown):
    assert shown["search_rows"] == 1
    assert shown["reopened"] is True
    assert shown["reopened_headline"] == "2 files didn't arrive as expected."
    assert shown["reopened_note_button"] == "Start incident note"
    assert shown["reopened_details_hidden"] is True        # no live tool messages for an earlier check


def test_what_the_check_proves_is_shown_in_manifest_doctors_own_words(shown):
    assert shown["rs_proves_shown"] is True
    assert shown["rs_proved"] == ("4 of the 5 files listed in the manifest were read in full and their MD5 "
                                  "checksums compared: 3 matched and 1 didn't.")
    assert shown["rs_not_checked_shown"] is True
    assert shown["rs_not_checked"] == ["1 listed file wasn't found, so it couldn't be compared."]
    assert shown["rs_cant_tell"].startswith("This shows the files match the manifest today.")
    assert shown["ac_proves_shown"] is True and shown["ac_not_checked_hidden"] is True
    assert shown["ac_proved"] == ("All 4 files listed in the manifest were found and read in full, "
                                  "and every MD5 checksum matched.")


def test_a_report_from_before_it_existed_shows_no_proves_panel(shown):
    assert shown["old_report_opened"] is True and shown["old_report_proves_hidden"] is True
