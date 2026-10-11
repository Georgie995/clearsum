"""Module 4: the incident note and the email, done entirely through the real window.
The clipboard and the mail app are stand-ins, so running this never touches either."""

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

import pytest

from clearsum import paths

DRIVER = Path(__file__).with_name("note_driver.py")

pytestmark = [
    pytest.mark.skipif(os.name != "nt", reason="the app is Windows-first; its window test needs Windows"),
    pytest.mark.skipif(not (paths.DELIVERY_DESK / "delivery_desk").is_dir()
                       or not (paths.MANIFEST_DOCTOR / "manifest_doctor").is_dir(),
                       reason="delivery-desk and manifest-doctor must sit next to the app"),
]


@pytest.fixture(scope="module")
def shown(tmp_path_factory):
    folder = tmp_path_factory.mktemp("note")
    out = folder / "result.json"
    subprocess.run([sys.executable, str(DRIVER), str(out), str(folder)], timeout=240, check=True)
    return json.loads(out.read_text(encoding="utf-8"))


def test_starting_the_note_opens_at_the_first_question_with_the_private_part(shown):
    assert shown["note_screen"] is True
    assert shown["first_question"] == "When it happened"
    assert shown["still_empty_at_start"].startswith("Still empty: When it happened, How it happened")
    assert "CAUSE_DUPLICATE_LISTING" in shown["private_causes"]


def test_the_email_has_the_subject_and_the_six_parts_in_order(shown):
    assert shown["email_screen"] is True
    assert shown["subject"] == "Delivery issue: clip_0004 overwritten on re-delivery (PROBLEMS FOUND)"
    headings = [part.split(":")[0] for part in shown["parts"]]
    assert headings == ["The problem", "Which delivery", "When it happened", "How it happened",
                        "How we intend to fix it", "Most plausible way to do it"]
    assert shown["subject_question_uses_one_line"] is True


def test_my_words_and_my_rewording_go_into_the_email_unchanged(shown):
    assert "Two errors, both on clip_0004.mov." in shown["parts"][0]
    assert "Re-deliver the first version under a different name." in shown["parts"][4]


def test_an_answer_that_looks_like_code_is_just_text_in_the_email(shown):
    assert "<img src=x onerror=" in shown["parts"][3]
    assert shown["images_in_email"] == 0 and shown["title_after_email"] == "ClearSum"


def test_copy_and_open_in_mail_app_use_the_email_and_never_send_it(shown):
    [copied] = shown["copied"]
    assert copied.startswith("Subject: Delivery issue: clip_0004 overwritten")
    assert shown["copy_label"] == "Copied"
    [url] = shown["opened"]
    assert url.startswith("mailto:?subject=") and "clip_0004 overwritten on re-delivery" in unquote(url)
    assert shown["file"] == "manager-email.txt"


def test_an_edit_made_in_notepad_meanwhile_is_kept_and_shown(shown):
    assert shown["q1_after_notepad"] == "Changed in Notepad."
    assert "manager-email.txt" in shown["note_files"] and "incident-note.md" in shown["note_files"]


def test_typing_over_a_note_changed_in_notepad_is_refused_and_the_latest_text_shown(shown):
    assert "was changed somewhere else" in shown["conflict_message"]
    assert shown["q3_after_conflict"] == "Fix typed in Notepad."
    assert shown["file_kept_notepad_fix"] is True


def test_the_recent_list_says_email_ready_once_the_email_is_made(shown):
    [item] = shown["recent_after_email"]
    assert "Email ready" in item
