"""Earlier checks, read straight from the reports folder each time.

No database: every check already leaves its report folder (report.json, and for problems an
incident note and maybe an email), so the list can never disagree with the files themselves.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

from . import paths
from .results import REPORT_ID, when_text

MAX_LISTED = 200     # the newest 200 are plenty to find this week's incident; all are counted
_headers = {}        # report.json headers already read, by (path, size, modified time)


def list_checks(reports_dir, now=None):
    now = now or datetime.now().astimezone()
    reports = Path(reports_dir)
    if not reports.is_dir():
        return {"ok": True, "folder": str(reports), "checks": [], "total": 0}
    folders = sorted((p for p in reports.iterdir()
                      if p.is_dir() and REPORT_ID.fullmatch(p.name) and (p / "report.json").is_file()),
                     key=lambda p: p.name, reverse=True)   # manifest-doctor names folders by date and time
    checks = [c for c in (_describe(f, now) for f in folders[:MAX_LISTED]) if c]
    checks.sort(key=lambda c: c["sort_key"], reverse=True)
    return {"ok": True, "folder": str(reports), "checks": checks, "total": len(folders)}


def _describe(folder, now):
    header = _header(folder / "report.json")
    if header is None:
        return None  # half-written or damaged: skipped quietly, the folder itself is untouched
    tree = str(header.get("tree") or "")
    note, state = _note_status(folder, header.get("result"))
    run_at = header.get("run_at") or ""
    return {"report_id": folder.name, "sort_key": run_at or folder.name,
            "when": _relative_day(run_at, now), "checked_at": when_text(run_at),
            "delivery": tree.replace("\\", "/").rstrip("/").split("/")[-1] or tree, "delivery_path": tree,
            "manifests": [m.get("path") for m in header.get("manifests") or []],
            "result": header.get("result"), "note": note, "note_state": state}


def _header(path):
    stat = path.stat()
    key = (str(path), stat.st_size, stat.st_mtime_ns)
    if key not in _headers:
        try:
            _headers[key] = json.loads(path.read_text(encoding="utf-8"))["header"]
        except (OSError, ValueError, KeyError, TypeError):
            return None
    return _headers[key]


def _note_status(folder, result):
    """Where the incident note is up to, in the words the list shows."""
    if any(folder.glob("manager-email*.txt")):
        return "Email ready", "email_ready"
    note_file = folder / "incident-note.md"
    if not note_file.is_file():
        return ("No note" if result == "PROBLEMS FOUND" else "No note needed"), "none"
    note = paths.load_engine("note")
    try:
        sections = note.read_sections(note_file.read_text(encoding="utf-8-sig"))
    except (note.NoteError, OSError, ValueError):
        return "Note needs attention", "attention"
    answered = len(note.MINE) - len(note.empty_sections(sections))
    if answered == 0:
        return "Not started", "not_started"
    return f"{answered} of {len(note.MINE)} answered", "in_progress"


def _relative_day(run_at, now):
    try:
        day = datetime.fromisoformat(run_at).astimezone(now.tzinfo).date()
    except (TypeError, ValueError):
        return ""
    if day == now.date():
        return "today"
    if day == now.date() - timedelta(days=1):
        return "yesterday"
    return f"{day.day} {day:%b}" + ("" if day.year == now.year else f" {day.year}")
