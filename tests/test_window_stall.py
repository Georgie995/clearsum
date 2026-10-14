"""The stuck warning in the real window (it opens for about half a minute, then closes).
A stand-in engine gets "stuck"; the time limit is cut to 3 seconds for this test only."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

DRIVER = Path(__file__).with_name("stall_driver.py")

pytestmark = pytest.mark.skipif(os.name != "nt", reason="the app is Windows-first; its window test needs Windows")


@pytest.fixture(scope="module")
def shown(tmp_path_factory):
    folder = tmp_path_factory.mktemp("stall")
    out = folder / "result.json"
    subprocess.run([sys.executable, str(DRIVER), str(out), str(folder)], timeout=120, check=True)
    return json.loads(out.read_text(encoding="utf-8"))


def test_the_warning_appears_only_once_nothing_has_moved_for_the_time_limit(shown):
    assert shown["checking_screen"] is True
    assert shown["hidden_at_first"] is True
    assert shown["appeared"] is True


def test_the_warning_names_the_file_as_plain_text_and_says_stopping_is_safe(shown):
    assert shown["text"].startswith("Nothing has been read from ShowA/<img src=x onerror=")
    assert "The storage may be stuck" in shown["text"] and "Stopping is safe" in shown["text"]
    assert shown["file_in_mono"] == ["ShowA/<img src=x onerror=\"document.title='INJECTED'\">.mov"]
    assert shown["images_in_warning"] == 0 and shown["title"] == "ClearSum"


def test_the_warning_clears_when_reading_resumes_and_stop_still_works(shown):
    assert shown["cleared_when_reading_resumed"] is True
    assert shown["stopped_back_to_start"] is True and shown["hidden_after_stop"] is True
