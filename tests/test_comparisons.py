"""The Compare lists screen's data: manifest-doctor's comparison of two list versions, shaped for the page.
Uses the real manifest-doctor next to the app. Synthetic lists only."""

import hashlib

import pytest

from clearsum import comparisons, paths

pytestmark = pytest.mark.skipif(not (paths.MANIFEST_DOCTOR / "manifest_doctor").is_dir(),
                                reason="manifest-doctor must sit next to the app")

GROUP_TITLES = ["Changed", "Renamed or moved", "Only in the earlier list", "Only in the later list",
                "Can't tell which became which", "Empty files"]


def md5(text):
    return hashlib.md5(text.encode()).hexdigest()


def compared(tmp_path, earlier, later, earlier_lines=()):
    comparer = paths.load_comparer()
    files = []
    for name, entries, extra in (("earlier.md5", earlier, earlier_lines), ("later.md5", later, ())):
        path = tmp_path / name
        path.write_text("\n".join([f"{p}|{h}" for p, h in entries] + list(extra)) + "\n", encoding="utf-8")
        files.append(path)
    return comparer.write_comparison(comparer.compare_lists(*files), tmp_path / "reports")


A = ("Reel01/a.mov", md5("a"))


def test_the_view_has_the_result_both_lists_and_every_group_in_order(tmp_path):
    folder = compared(tmp_path, [A, ("Reel01/b.mov", md5("b")), ("Reel01/old.mov", md5("x"))],
                      [A, ("Reel01/b.mov", md5("b2")), ("Reel01/new.mov", md5("x")), ("Reel01/c.mov", md5("c"))])
    view = comparisons.summarise(folder)
    assert view["ok"] is True and view["compare_id"] == folder.name
    assert (view["result"], view["identical"]) == ("THE LISTS DIFFER", False)
    assert (view["earlier"]["name"], view["later"]["name"], view["later"]["entries"]) == ("earlier.md5", "later.md5", 4)
    assert [g["title"] for g in view["groups"]] == GROUP_TITLES
    changed, renamed, _, only_later, _, _ = view["groups"]
    assert changed["rows"] == [{"earlier": "Reel01/b.mov", "later": "Reel01/b.mov", "note": ""}]
    assert renamed["rows"] == [{"earlier": "Reel01/old.mov", "later": "Reel01/new.mov", "note": ""}]
    assert only_later["rows"] == [{"earlier": "", "later": "Reel01/c.mov", "note": ""}]
    assert view["unchanged"] == 1
    assert view["limits"].startswith("This compares the names and checksums written in the two lists.")


def test_every_group_explains_itself_in_plain_words(tmp_path):
    view = comparisons.summarise(compared(tmp_path, [A], [A]))
    explained = {g["title"]: g["explain"] for g in view["groups"]}
    assert explained["Changed"] == "Same name, different checksum. This is usually where a problem came in."
    assert explained["Empty files"] == "All empty files share one checksum, so they're never paired."
    assert view["identical"] is True and all(g["total"] == 0 for g in view["groups"])


def test_a_changed_files_earlier_content_found_elsewhere_is_in_its_note(tmp_path):
    folder = compared(tmp_path, [("Reel01/clip_0004.mov", md5("v1"))],
                      [("Reel01/clip_0004.mov", md5("v2")), ("Reel01/clip_0004_v1.mov", md5("v1"))])
    changed = comparisons.summarise(folder)["groups"][0]
    assert changed["rows"][0]["note"] == "Its earlier content is now at Reel01/clip_0004_v1.mov."


def test_groups_that_cant_be_told_apart_are_one_row_each_with_short_checksums(tmp_path):
    folder = compared(tmp_path, [("Reel01/b.mov", md5("v1")), ("Reel01/b.mov", md5("v2"))],
                      [("Reel01/b.mov", md5("v2"))])
    [row] = comparisons.summarise(folder)["groups"][4]["rows"]
    assert row["earlier"] == "Reel01/b.mov\nReel01/b.mov" and row["later"] == "Reel01/b.mov"
    assert row["note"] == (f"Listed more than once. Checksums: earlier {md5('v1')[:8]}…, {md5('v2')[:8]}…; "
                           f"later {md5('v2')[:8]}….")


def test_long_groups_are_shortened_on_screen_but_counted(tmp_path, monkeypatch):
    monkeypatch.setattr(comparisons, "MAX_ROWS", 2)
    folder = compared(tmp_path, [A], [A] + [(f"Reel01/{n}.mov", md5(n)) for n in "xyz"])
    only_later = comparisons.summarise(folder)["groups"][3]
    assert (len(only_later["rows"]), only_later["total"]) == (2, 3)


def test_notes_about_unreadable_lines_and_the_folder_hint_come_through(tmp_path):
    folder = compared(tmp_path, [("/Volumes/RAID/SHOW/Reel01/a.mov", md5("a"))], [A],
                      earlier_lines=["Reel01/cut|0123"])
    view = comparisons.summarise(folder)
    assert view["notes"] == ["1 line in the earlier list couldn't be read, so the file it describes may wrongly "
                             "show as only in the later list."]
    assert view["hint"].startswith("Every renamed file's earlier name is its later name with")


# --- "Where did X go?": search every group, unchanged included -----------------------------------

def test_search_finds_a_file_in_any_group_whatever_the_case(tmp_path):
    folder = compared(tmp_path, [A, ("Reel01/OLD_Take.mov", md5("x"))], [A, ("Reel01/new.mov", md5("x"))])
    assert comparisons.search(folder, "a.mov") == {"total": 1, "rows": [
        {"group": "Unchanged", "earlier": "Reel01/a.mov", "later": "Reel01/a.mov", "note": ""}]}
    assert comparisons.search(folder, "old_take")["rows"][0]["group"] == "Renamed or moved"   # case doesn't matter
    assert comparisons.search(folder, "  ") == {"total": 0, "rows": []}


def test_search_results_are_capped_but_counted(tmp_path, monkeypatch):
    monkeypatch.setattr(comparisons, "MAX_SEARCH", 2)
    folder = compared(tmp_path, [(f"Reel01/clip_{n}.mov", md5(n)) for n in "123"],
                      [(f"Reel01/clip_{n}.mov", md5(n)) for n in "123"])
    found = comparisons.search(folder, "clip")
    assert (found["total"], len(found["rows"])) == (3, 2)
