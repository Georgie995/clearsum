"""Module 4: the incident note and the manager email, through delivery-desk's own tested code."""

import json
from urllib.parse import unquote

import pytest

from clearsum import paths
from clearsum.bridge import Bridge
from clearsum.notes import mailto_url

pytestmark = pytest.mark.skipif(not (paths.DELIVERY_DESK / "delivery_desk").is_dir(),
                                reason="delivery-desk must sit next to the app")

ANSWERS = {
    "When it happened": "Delivered on 3 October. Re-delivered on 9 October.",
    "How it happened": "clip_0004.mov exists on two tapes with different content.",
    "How we intend to fix it": "Re-deliver the first version under a different name.",
    "Most plausible way to do it": "Restore it from tape 1, rename it clip_0004_v1.mov, and upload it.",
    "Subject summary": "clip_0004 overwritten on re-delivery",
}


@pytest.fixture
def desk(tmp_path, secrets):
    """A report folder with a working note, written by delivery-desk's own note code."""
    paths.load_engine()
    from delivery_desk.note import build_note, write_note
    reports = tmp_path / "reports"
    folder = reports / "report-2026-10-11_160742"
    folder.mkdir(parents=True)
    report = {"header": {"result": "PROBLEMS FOUND", "tree": "D:/Deliveries/show-a-ep01",
                         "run_at": "2026-10-11T16:07:42+01:00", "counts": {"ERROR": 2, "WARNING": 0, "INFO": 0},
                         "manifests": [{"path": "set1.md5", "entries": 5}]},
              "causes": [{"code": "CAUSE_DUPLICATE_LISTING", "severity": "ERROR", "summary": "listed twice",
                          "paths": ["ShowA/Reel01/clip_0004.mov"]}],
              "findings": [{"code": "DUPLICATE_ENTRY", "severity": "ERROR", "path": "ShowA/Reel01/clip_0004.mov"},
                           {"code": "HASH_MISMATCH", "severity": "ERROR", "path": "ShowA/Reel01/clip_0004.mov"}]}
    (folder / "report.json").write_text(json.dumps(report), encoding="utf-8")
    write_note(folder, build_note(report))
    copied, opened = [], []
    b = Bridge(settings_file=tmp_path / "app" / "settings.json", secrets=secrets,
               clipboard=copied.append, opener=opened.append)
    b.save_settings({"reports_dir": str(reports)})
    b.folder, b.copied, b.opened = folder, copied, opened
    return b


def answer_all(b):
    for heading, text in ANSWERS.items():
        view = b.save_answer(b.folder.name, heading, text, "")
        assert view["ok"], view
    return view


def test_the_note_shows_the_check_parts_empty_answers_and_the_private_part(desk):
    view = desk.get_note(desk.folder.name)
    assert view["from_check"]["The problem"].startswith("PROBLEMS FOUND: 2 errors")
    assert view["answers"] == {h: "" for h in ANSWERS}            # placeholders are shown as empty boxes
    assert view["empty"] == list(ANSWERS)
    assert "listed twice" in view["private"]["causes"]
    assert [q["heading"] for q in view["questions"]] == list(ANSWERS)


def test_each_answer_is_saved_into_the_note_straight_away(desk):
    view = desk.save_answer(desk.folder.name, "When it happened", ANSWERS["When it happened"], "")
    assert view["answers"]["When it happened"] == ANSWERS["When it happened"]
    assert ANSWERS["When it happened"] in (desk.folder / "incident-note.md").read_text(encoding="utf-8")


def test_an_answer_changed_in_a_text_editor_meanwhile_is_never_overwritten(desk):
    note = desk.folder / "incident-note.md"
    note.write_text(note.read_text(encoding="utf-8").replace("## How it happened\n(fill in)",
                                                              "## How it happened\nTyped in Notepad."), encoding="utf-8")
    result = desk.save_answer(desk.folder.name, "How it happened", "Typed in the app.", "")
    assert result["ok"] is False and result["conflict"] is True
    assert "Typed in Notepad." in note.read_text(encoding="utf-8")
    assert result["note"]["answers"]["How it happened"] == "Typed in Notepad."   # the page can show the latest


def test_going_back_and_changing_an_answer_works(desk):
    desk.save_answer(desk.folder.name, "When it happened", "First try.", "")
    view = desk.save_answer(desk.folder.name, "When it happened", "Second try.", "First try.")
    assert view["answers"]["When it happened"] == "Second try."


def test_the_subject_summary_is_kept_to_one_line(desk):
    view = desk.save_answer(desk.folder.name, "Subject summary", "clip_0004\noverwritten", "")
    assert view["answers"]["Subject summary"] == "clip_0004 overwritten"
    assert view["subject_preview"] == "Delivery issue: clip_0004 overwritten (PROBLEMS FOUND)"


def test_the_email_isnt_made_until_all_five_are_answered(desk):
    desk.save_answer(desk.folder.name, "When it happened", ANSWERS["When it happened"], "")
    result = desk.make_email(desk.folder.name)
    assert result["ok"] is False and result["missing"] == list(ANSWERS)[1:]
    assert not list(desk.folder.glob("manager-email*"))


def test_the_email_has_the_subject_and_six_parts_with_my_words_unchanged(desk):
    answer_all(desk)
    email = desk.make_email(desk.folder.name)
    assert email["subject"] == "Delivery issue: clip_0004 overwritten on re-delivery (PROBLEMS FOUND)"
    assert [p["heading"] for p in email["parts"]] == ["The problem", "Which delivery", "When it happened",
                                                      "How it happened", "How we intend to fix it",
                                                      "Most plausible way to do it"]
    assert email["parts"][2]["text"] == ANSWERS["When it happened"]
    assert (desk.folder / email["file"]).read_text(encoding="utf-8").startswith("Subject: Delivery issue:")


def test_making_the_email_again_never_overwrites_the_first(desk):
    answer_all(desk)
    assert desk.make_email(desk.folder.name)["file"] == "manager-email.txt"
    assert desk.make_email(desk.folder.name)["file"] == "manager-email-2.txt"


def test_copy_puts_the_latest_email_on_the_clipboard(desk):
    answer_all(desk)
    desk.make_email(desk.folder.name)
    assert desk.copy_email(desk.folder.name) == {"ok": True}
    [text] = desk.copied
    assert text.startswith("Subject: Delivery issue: clip_0004") and ANSWERS["How it happened"] in text


def test_open_in_mail_app_fills_the_subject_and_body_when_they_fit(desk):
    answer_all(desk)
    desk.make_email(desk.folder.name)
    result = desk.open_email(desk.folder.name)
    assert result == {"ok": True, "body_included": True}
    [url] = desk.opened
    assert url.startswith("mailto:?subject=") and "clip_0004 overwritten" in unquote(url)
    assert ANSWERS["How it happened"] in unquote(url)


def test_a_long_email_opens_with_the_subject_only_and_is_copied_for_pasting(desk):
    long_text = "Restore it from tape 1. " * 200
    answers = dict(ANSWERS, **{"Most plausible way to do it": long_text})
    for heading, text in answers.items():
        desk.save_answer(desk.folder.name, heading, text, "")
    desk.make_email(desk.folder.name)
    result = desk.open_email(desk.folder.name)
    assert result == {"ok": True, "body_included": False}
    assert "body=" not in desk.opened[0]
    assert desk.copied and long_text.strip() in desk.copied[0]


def test_the_mail_link_is_safely_encoded():
    url, included = mailto_url("A & B: 50% done?", "Line one\nLine two & more")
    assert included is True
    assert url.startswith("mailto:?subject=A%20%26%20B%3A%2050%25%20done%3F&body=")
    assert "%0D%0A" in url and "&" not in url.split("&body=")[1]


def test_notes_and_emails_are_only_reached_through_real_report_folders(desk):
    for sneaky in ("..", r"..\..\Windows", "report-x/../../app", None):
        assert desk.get_note(sneaky)["ok"] is False
        assert desk.make_email(sneaky)["ok"] is False
        assert desk.copy_email(sneaky)["ok"] is False
        assert desk.open_email(sneaky)["ok"] is False
    assert desk.opened == [] and desk.copied == []
