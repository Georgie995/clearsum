"""Module 3: turning a report.json into what the All clear / Problems found screens show."""

import json

from clearsum import results


def finding(code, path, severity="ERROR", detail=""):
    return {"code": code, "severity": severity, "path": path, "detail": detail}


def write_report(folder, result, findings=(), causes=(), entries=1204):
    folder.mkdir(parents=True)
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in ("ERROR", "WARNING", "INFO")}
    report = {"header": {"result": result, "tree": "D:/Deliveries/show-a-ep01", "run_at": "2026-10-11T16:07:42+01:00",
                         "counts": counts, "manifests": [{"path": "set1.md5", "entries": entries}]},
              "causes": list(causes), "findings": list(findings)}
    (folder / "report.json").write_text(json.dumps(report), encoding="utf-8")
    return folder


def test_a_clean_delivery_says_every_file_matches(tmp_path):
    view = results.summarise(write_report(tmp_path / "report-1", "CLEAN"))
    assert view["headline"] == "All 1,204 files match the manifest."
    assert view["result"] == "CLEAN" and view["checked_at"] == "11 Oct 2026 at 16:07"
    assert all(c["count"] == 0 for c in view["categories"])


def test_warnings_only_say_every_file_arrived_intact(tmp_path):
    view = results.summarise(write_report(tmp_path / "report-1", "PASSED WITH WARNINGS",
                                          [finding("EXTRA", "a/.junk", "WARNING")]))
    assert view["headline"] == "Every file arrived intact."
    assert view["subline"] == "1 warning worth a look."


def test_problems_count_the_files_affected_not_the_findings(tmp_path):
    view = results.summarise(write_report(tmp_path / "report-1", "PROBLEMS FOUND", [
        finding("DUPLICATE_ENTRY", "ShowA/clip_0004.mov"), finding("HASH_MISMATCH", "ShowA/clip_0004.mov"),
        finding("HIDDEN_FILE", "ShowA/.DS_Store", "INFO")]))
    assert view["headline"] == "1 file didn't arrive as expected."
    assert [r["severity"] for r in view["findings"]] == ["ERROR", "ERROR", "INFO"]
    assert view["findings"][0]["title"] == "Listed twice in a manifest, with different checksums"


def test_problems_only_in_the_manifest_itself_are_said_plainly(tmp_path):
    view = results.summarise(write_report(tmp_path / "report-1", "PROBLEMS FOUND",
                                          [finding("MANIFEST_LINE_UNREADABLE", None)]))
    assert view["headline"] == "The manifest itself has problems."


def test_causes_get_friendly_titles_and_long_file_lists_are_cut(tmp_path):
    cause = {"code": "CAUSE_DUPLICATE_LISTING", "severity": "ERROR", "summary": "listed twice",
             "paths": [f"ShowA/clip_{i:04}.mov" for i in range(14)]}
    view = results.summarise(write_report(tmp_path / "report-1", "PROBLEMS FOUND",
                                          [finding("DUPLICATE_ENTRY", "ShowA/clip_0000.mov")], [cause]))
    [shown] = view["causes"]
    assert shown["title"] == "A file is listed twice in the manifest, with different checksums"
    assert len(shown["paths"]) == 10 and shown["more"] == 4


def test_a_huge_number_of_findings_is_capped_but_counted(tmp_path):
    many = [finding("MISSING", f"ShowA/clip_{i:05}.mov") for i in range(2000)]
    view = results.summarise(write_report(tmp_path / "report-1", "PROBLEMS FOUND", many))
    assert len(view["findings"]) == results.MAX_ROWS and view["findings_total"] == 2000


def test_a_working_note_beside_the_report_is_noticed(tmp_path):
    folder = write_report(tmp_path / "report-1", "PROBLEMS FOUND", [finding("MISSING", "a.mov")])
    assert results.summarise(folder)["has_note"] is False
    (folder / "incident-note.md").write_text("note", encoding="utf-8")
    assert results.summarise(folder)["has_note"] is True


def test_file_names_pass_through_as_plain_data(tmp_path):
    name = '<img src=x onerror="alert(1)">.mov'
    view = results.summarise(write_report(tmp_path / "report-1", "PROBLEMS FOUND", [finding("MISSING", name)]))
    assert view["findings"][0]["path"] == name
