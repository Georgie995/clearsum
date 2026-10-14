"""Module 2: what happens when something is dropped on a card (tested without a window)."""

import json
import re

from clearsum.app import _on_drop


class FakeWindow:
    def __init__(self):
        self.calls = []

    def run_js(self, code):
        self.calls.append(code)


class FakeBridge:
    def describe_folder(self, path):
        return {"ok": True, "name": "show-a-ep01", "path": path, "files": 3}

    def describe_manifest(self, path):
        return {"ok": True, "name": "set1.md5", "path": path, "entries": 3}


def dropped(kind, files):
    window = FakeWindow()
    _on_drop(window, FakeBridge(), kind)({"dataTransfer": {"files": files}})
    [code] = window.calls
    match = re.fullmatch(r"window\.app\.dropped\((.*?), (.*)\)", code, re.S)
    return json.loads(match.group(1)), json.loads(match.group(2))


def test_one_dropped_folder_is_described_by_the_bridge():
    kind, info = dropped("folder", [{"name": "show-a-ep01", "pywebviewFullPath": "D:\\Deliveries\\show-a-ep01"}])
    assert kind == "folder" and info["path"] == "D:\\Deliveries\\show-a-ep01" and info["files"] == 3


def test_a_dropped_manifest_goes_to_the_manifest_description():
    kind, info = dropped("manifest", [{"name": "set1.md5", "pywebviewFullPath": "D:\\Deliveries\\set1.md5"}])
    assert kind == "manifest" and info["entries"] == 3


def test_several_items_at_once_get_a_plain_message():
    _, info = dropped("folder", [{"pywebviewFullPath": "D:\\a"}, {"pywebviewFullPath": "D:\\b"}])
    assert info == {"ok": False, "error": "Add one item at a time."}


def test_a_drop_without_a_real_location_points_to_the_choose_button():
    _, info = dropped("manifest", [{"name": "from-a-browser.md5"}])
    assert "Choose button" in info["error"]


def test_a_file_name_with_quotes_and_script_tags_cannot_break_out_of_the_call():
    nasty = 'D:\\x\\a"); document.title=("pwned</script>\u2028.md5'
    kind, info = dropped("manifest", [{"pywebviewFullPath": nasty}])
    assert info["path"] == nasty                       # arrived intact, as data


def test_a_list_dropped_on_the_compare_screen_is_described_like_a_manifest():
    for side in ("earlier", "later"):
        kind, info = dropped(side, [{"pywebviewFullPath": "D:\\Lists\\v1.md5"}])
        assert kind == side and info["entries"] == 3
