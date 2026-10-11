"""Module 5: Earlier checks, read straight from the reports folder (no database to drift)."""

import json
from datetime import datetime

import pytest

from delivery_desk_app import history, paths
from delivery_desk_app.bridge import Bridge

pytestmark = pytest.mark.skipif(not (paths.DELIVERY_DESK / "delivery_desk").is_dir(),
                                reason="delivery-desk must sit next to the app")

NOW = datetime.fromisoformat("2026-10-11T18:00:00+01:00")


def add_report(reports, stamp, result, tree="D:/Deliveries/show-a-ep01", note_answers=None, email=False):
    """A report folder as manifest-doctor writes it, optionally with a note (n answers) and an email."""
    folder = reports / f"report-{stamp}"
    folder.mkdir(parents=True)
    run_at = datetime.strptime(stamp, "%Y-%m-%d_%H%M%S").strftime("%Y-%m-%dT%H:%M:%S+01:00")
    report = {"header": {"result": result, "tree": tree, "run_at": run_at,
                         "counts": {"ERROR": 1 if result == "PROBLEMS FOUND" else 0, "WARNING": 0, "INFO": 0},
                         "manifests": [{"path": "set1.md5", "entries": 4}]},
              "causes": [], "findings": [{"code": "MISSING", "severity": "ERROR", "path": "a.mov"}]
              if result == "PROBLEMS FOUND" else []}
    (folder / "report.json").write_text(json.dumps(report), encoding="utf-8")
    if note_answers is not None:
        paths.load_engine()
        from delivery_desk.note import MINE, build_note, set_section
        text = build_note(report)
        for heading in MINE[:note_answers]:
            text = set_section(text, heading, f"answer for {heading}")
        (folder / "incident-note.md").write_text(text, encoding="utf-8")
    if email:
        (folder / "manager-email.txt").write_text("Subject: Delivery issue: x (PROBLEMS FOUND)\n", encoding="utf-8")
    return folder


def test_an_empty_or_missing_reports_folder_lists_nothing(tmp_path):
    assert history.list_checks(tmp_path / "nowhere", now=NOW)["checks"] == []
    (tmp_path / "reports").mkdir()
    assert history.list_checks(tmp_path / "reports", now=NOW)["checks"] == []


def test_checks_are_listed_newest_first_with_where_the_note_is_up_to(tmp_path):
    reports = tmp_path / "reports"
    add_report(reports, "2026-10-09_101500", "CLEAN", tree="D:/Deliveries/show-a-ep02")
    add_report(reports, "2026-10-10_090000", "PROBLEMS FOUND", note_answers=5, email=True)
    add_report(reports, "2026-10-11_160742", "PROBLEMS FOUND", note_answers=3)
    add_report(reports, "2026-10-11_170000", "PROBLEMS FOUND", note_answers=0)
    checks = history.list_checks(reports, now=NOW)["checks"]
    assert [c["report_id"] for c in checks] == ["report-2026-10-11_170000", "report-2026-10-11_160742",
                                                "report-2026-10-10_090000", "report-2026-10-09_101500"]
    assert [c["note"] for c in checks] == ["Not started", "3 of 5 answered", "Email ready", "No note needed"]
    assert [c["when"] for c in checks] == ["today", "today", "yesterday", "9 Oct"]
    assert checks[3]["delivery"] == "show-a-ep02" and checks[3]["delivery_path"] == "D:/Deliveries/show-a-ep02"
    assert checks[0]["manifests"] == ["set1.md5"] and checks[0]["result"] == "PROBLEMS FOUND"


def test_folders_that_arent_finished_reports_are_skipped_quietly(tmp_path):
    reports = tmp_path / "reports"
    add_report(reports, "2026-10-11_160742", "CLEAN")
    (reports / "report-2026-10-11_170000").mkdir()                 # interrupted: no report.json
    (reports / "outbox").mkdir()                                   # not a report folder at all
    broken = reports / "report-2026-10-11_180000"
    broken.mkdir()
    (broken / "report.json").write_text("{ half", encoding="utf-8")
    assert [c["report_id"] for c in history.list_checks(reports, now=NOW)["checks"]] == ["report-2026-10-11_160742"]


def test_a_note_whose_headings_were_changed_by_hand_is_flagged_not_hidden(tmp_path):
    folder = add_report(tmp_path / "reports", "2026-10-11_160742", "PROBLEMS FOUND", note_answers=1)
    note = folder / "incident-note.md"
    note.write_text(note.read_text(encoding="utf-8").replace("## How it happened", "## Cause"), encoding="utf-8")
    [check] = history.list_checks(tmp_path / "reports", now=NOW)["checks"]
    assert check["note"] == "Note needs attention"


def test_only_the_newest_two_hundred_are_listed_but_all_are_counted(tmp_path):
    reports = tmp_path / "reports"
    for i in range(205):
        add_report(reports, f"2026-09-{1 + i // 24:02}_{i % 24:02}0000", "CLEAN")
    listed = history.list_checks(reports, now=NOW)
    assert len(listed["checks"]) == history.MAX_LISTED == 200 and listed["total"] == 205


def test_dates_from_earlier_years_say_the_year(tmp_path):
    add_report(tmp_path / "reports", "2025-12-30_101500", "CLEAN")
    assert history.list_checks(tmp_path / "reports", now=NOW)["checks"][0]["when"] == "30 Dec 2025"


def test_the_bridge_lists_the_reports_folder_in_use(tmp_path, secrets, hub):
    add_report(tmp_path / "mine", "2026-10-11_160742", "CLEAN")
    add_report(tmp_path / "hub-reports", "2026-10-11_170000", "PROBLEMS FOUND")
    b = Bridge(settings_file=tmp_path / "app" / "settings.json", secrets=secrets)
    b.save_settings({"reports_dir": str(tmp_path / "mine")})
    assert [c["report_id"] for c in b.list_checks()["checks"]] == ["report-2026-10-11_160742"]
    b.save_settings({"reports_dir": str(tmp_path / "mine"), "ops_hub_path": str(hub[0]), "ops_hub_config": str(hub[1])})
    listed = b.list_checks()
    assert [c["report_id"] for c in listed["checks"]] == ["report-2026-10-11_170000"]
    assert listed["folder"] == str(tmp_path / "hub-reports")


def test_delivery_names_pass_through_as_plain_data(tmp_path):
    add_report(tmp_path / "reports", "2026-10-11_160742", "CLEAN", tree="D:/Deliveries/<img src=x onerror=alert(1)>")
    [check] = history.list_checks(tmp_path / "reports", now=NOW)["checks"]
    assert check["delivery"] == "<img src=x onerror=alert(1)>"
