"""Turn a check's report.json into what the All clear and Problems found screens show.

Everything a delivery contributes (file names, details) is passed on as plain data; the page
always shows it as text.
"""

import json
import re
from datetime import datetime
from pathlib import Path

from . import titles

REPORT_ID = re.compile(r"report-[A-Za-z0-9_\-]+")  # manifest-doctor's report folder names, nothing else

MAX_ROWS = 500        # enough to read on screen; the full list is always in the report files
MAX_PATHS = 10        # per probable cause, as in the working note
SEVERITY_ORDER = {"ERROR": 0, "WARNING": 1, "INFO": 2}


def summarise(folder):
    folder = Path(folder)
    report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    header, findings = report["header"], report["findings"]
    entries = sum(m.get("entries") or 0 for m in header.get("manifests") or [])
    headline, subline = _headline(header, findings, entries)
    rows = sorted(findings, key=lambda f: (SEVERITY_ORDER.get(f["severity"], 3), f.get("path") or ""))
    return {
        "ok": True,
        "report_id": folder.name,
        "result": header["result"],
        "headline": headline,
        "subline": subline,
        "tree": header.get("tree"),
        "manifests": [m.get("path") for m in header.get("manifests") or []],
        "checked_at": when_text(header.get("run_at")),
        "counts": header.get("counts", {}),
        "causes": [_cause(c) for c in report.get("causes", [])],
        "findings": [{"severity": f["severity"], "code": f["code"], "title": titles.title(f["code"]),
                      "path": f.get("path"), "detail": f.get("detail") or ""} for f in rows[:MAX_ROWS]],
        "findings_total": len(findings),
        "categories": titles.count_by_category(findings),
        "has_note": (folder / "incident-note.md").exists(),
        "proves": _proves(header.get("coverage")),
    }


def _proves(coverage):
    """What the check proves, in manifest-doctor's own approved words. Older reports don't say: None."""
    if not coverage:
        return None
    return {"proved": coverage.get("proved", ""), "not_checked": list(coverage.get("not_checked") or []),
            "cannot_tell": coverage.get("cannot_tell", "")}


def _headline(header, findings, entries):
    result = header["result"]
    if result == "CLEAN":
        return (f"All {entries:,} files match the manifest." if entries else "Every file matches the manifest."), None
    if result == "PASSED WITH WARNINGS":
        warnings = header.get("counts", {}).get("WARNING", 0)
        return "Every file arrived intact.", f"{warnings:,} warning{'' if warnings == 1 else 's'} worth a look."
    # Count files, not findings: one bad file can have two findings (listed twice AND mismatched).
    affected = {f["path"] for f in findings if f["severity"] == "ERROR" and f.get("path")}
    if not affected:
        return "The manifest itself has problems.", None
    n = len(affected)
    return f"{n:,} file{'' if n == 1 else 's'} didn't arrive as expected.", None


def _cause(cause):
    paths = cause.get("paths") or []
    return {"code": cause["code"], "severity": cause["severity"], "title": titles.title(cause["code"]),
            "summary": cause.get("summary", ""), "paths": paths[:MAX_PATHS], "more": max(0, len(paths) - MAX_PATHS)}


def when_text(run_at):
    try:
        moment = datetime.fromisoformat(run_at)
    except (TypeError, ValueError):
        return run_at or ""
    return f"{moment.day} {moment:%b %Y} at {moment:%H:%M}"
