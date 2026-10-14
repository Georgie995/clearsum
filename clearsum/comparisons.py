"""Turn a saved comparison (manifest-doctor's comparison.json) into what the Compare lists screen shows,
and search it for "where did this file go?".

Every name comes from a list someone else made, so it's passed on as plain data: the page always
shows it as text.
"""

import json
import re
from pathlib import Path

from .results import when_text

COMPARE_ID = re.compile(r"compare-[A-Za-z0-9_\-]+")   # manifest-doctor's comparison folder names, nothing else
MAX_ROWS = 500       # per group on screen; comparison.csv always has every file
MAX_SEARCH = 200
GROUPS = [
    ("changed", "Changed", "Same name, different checksum. This is usually where a problem came in."),
    ("renamed", "Renamed or moved", "Same checksum, different name."),
    ("only_earlier", "Only in the earlier list", "Not paired with any file in the later list."),
    ("only_later", "Only in the later list", "Not paired with any file in the earlier list."),
    ("cannot_tell", "Can't tell which became which",
     "Several files share a checksum, or a name is listed more than once, so they're shown together "
     "rather than guessed."),
    ("empty", "Empty files", "All empty files share one checksum, so they're never paired."),
]


def summarise(folder):
    folder = Path(folder)
    data = _load(folder)
    header = data["header"]
    groups = []
    for key, title, explain in GROUPS:
        rows = list(_rows(key, data))
        groups.append({"key": key, "title": title, "explain": explain, "total": len(rows), "rows": rows[:MAX_ROWS]})
    return {"ok": True, "compare_id": folder.name, "result": header["result"], "identical": header["identical"],
            "earlier": _about(header["earlier"]), "later": _about(header["later"]),
            "compared_at": when_text(header.get("run_at")), "checksum": header.get("checksum"),
            "counts": header["counts"], "unchanged": header["counts"]["unchanged"],
            "notes": header.get("notes") or [], "hint": header.get("hint"), "limits": header.get("limits", ""),
            "groups": groups}


def search(folder, text):
    """Every file whose earlier or later name contains the text, in any group, unchanged included."""
    words = (text or "").strip().lower()
    if not words:
        return {"total": 0, "rows": []}
    data = _load(Path(folder))
    found = [{"group": title, **row}
             for key, title, _ in GROUPS + [("unchanged", "Unchanged", "")]
             for row in _rows(key, data)
             if words in row["earlier"].lower() or words in row["later"].lower()]
    return {"total": len(found), "rows": found[:MAX_SEARCH]}


def _load(folder):
    return json.loads((folder / "comparison.json").read_text(encoding="utf-8"))


def _about(side):
    return {"name": Path(side["path"]).name, "path": side["path"], "entries": side["entries"],
            "format": side.get("format")}


def _short(checksum):
    return checksum[:8] + "…"   # enough to tell versions apart on screen; the files have them in full


def _rows(key, data):
    if key == "changed":
        for x in data["changed"]:
            moved = x.get("earlier_content_now_at") or []
            yield {"earlier": x["path"], "later": x["path"],
                   "note": f"Its earlier content is now at {', '.join(moved)}." if moved else ""}
    elif key == "renamed":
        for x in data["renamed"]:
            yield {"earlier": x["earlier_path"], "later": x["later_path"], "note": ""}
    elif key == "only_earlier":
        for x in data["only_earlier"]:
            yield {"earlier": x["path"], "later": "", "note": ""}
    elif key == "only_later":
        for x in data["only_later"]:
            yield {"earlier": "", "later": x["path"], "note": ""}
    elif key == "cannot_tell":
        for g in data["cannot_tell"]:
            if "name" in g:
                note = (f"Listed more than once. Checksums: earlier {', '.join(map(_short, g['earlier_checksums']))}; "
                        f"later {', '.join(map(_short, g['later_checksums']))}.")
            else:
                note = f"Every file here has the checksum {_short(g['checksum'])}."
            yield {"earlier": "\n".join(g["earlier"]), "later": "\n".join(g["later"]), "note": note}
    elif key == "empty":
        for p in data["empty"]["earlier"]:
            yield {"earlier": p, "later": "", "note": ""}
        for p in data["empty"]["later"]:
            yield {"earlier": "", "later": p, "note": ""}
    elif key == "unchanged":
        for x in data["unchanged"]:
            yield {"earlier": x["path"], "later": x["path"], "note": ""}
