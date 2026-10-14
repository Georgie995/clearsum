"""The Compare lists screen in the real window (it opens for about half a minute, then closes).
Needs manifest-doctor next to the app. Synthetic lists only."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from clearsum import paths

DRIVER = Path(__file__).with_name("compare_driver.py")

pytestmark = [
    pytest.mark.skipif(os.name != "nt", reason="the app is Windows-first; its window test needs Windows"),
    pytest.mark.skipif(not (paths.MANIFEST_DOCTOR / "manifest_doctor").is_dir(),
                       reason="manifest-doctor must sit next to the app"),
]


@pytest.fixture(scope="module")
def shown(tmp_path_factory):
    folder = tmp_path_factory.mktemp("compare")
    out = folder / "result.json"
    subprocess.run([sys.executable, str(DRIVER), str(out), str(folder)], timeout=120, check=True)
    return json.loads(out.read_text(encoding="utf-8"))


def test_two_lists_are_added_like_the_start_screens_cards(shown):
    assert shown["compare_screen"] is True and shown["button_disabled_at_first"] is True
    assert shown["hint_after_one"] == "Now add the later list."
    assert shown["later_entries"] == "4 entries"


def test_the_result_lists_each_group_with_what_happened_to_each_file(shown):
    assert shown["results_shown"] is True
    assert shown["pill"] == "THE LISTS DIFFER"
    assert shown["headline"] == "4 files differ between the two lists."
    assert shown["group_titles"] == ["Changed · 1", "Renamed or moved · 1", "Only in the earlier list · 1",
                                     "Only in the later list · 1"]
    assert shown["changed_rows"] == [["ShowA/Reel01/clip_0002.mov", "ShowA/Reel01/clip_0002.mov", ""]]
    assert shown["renamed_rows"] == [["ShowA/Day 1 – Interviews/take 01.wav", "ShowA/Day_1_-_Interviews/take_01.wav", ""]]
    assert shown["unchanged"].startswith("1 file is unchanged")
    assert shown["limits"].startswith("This compares the names and checksums written in the two lists.")


def test_a_name_that_looks_like_code_is_just_text(shown):
    assert shown["only_later_rows"] == ["ShowA/<img src=x onerror=\"document.title='INJECTED'\">.mov"]
    assert shown["images"] == 0 and shown["title"] == "ClearSum"


def test_search_answers_where_did_a_file_go_and_says_when_nothing_matches(shown):
    assert shown["search_rows"] == [["Unchanged", "ShowA/Reel01/clip_0001.mov", "ShowA/Reel01/clip_0001.mov", ""]]
    assert shown["search_none"] == "No file in either list matches that."


def test_show_in_folder_and_compare_two_other_lists(shown):
    assert len(shown["opened"]) == 1 and shown["opened"][0].startswith("compare-")
    assert shown["fresh_again"] is True
