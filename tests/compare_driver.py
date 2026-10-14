"""Opens the real app, compares two made-up versions of a checksum list on the Compare lists screen,
and records what it shows. Run by test_window_compare.py in its own process. Synthetic lists only;
uses the real manifest-doctor next to the app."""

import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import webview  # noqa: E402

from clearsum.app import bind_drops, create_window  # noqa: E402
from clearsum.bridge import Bridge  # noqa: E402
from clearsum.secret_store import SecretStore  # noqa: E402
from window_driver import FakeKeyring  # noqa: E402

HOSTILE = "ShowA/<img src=x onerror=\"document.title='INJECTED'\">.mov"


def md5(text):
    return hashlib.md5(text.encode()).hexdigest()


def make_lists(root):
    earlier = root / "delivery_v1.md5"
    earlier.write_text("\n".join([
        f"ShowA/Reel01/clip_0001.mov|{md5('one')}",
        f"ShowA/Reel01/clip_0002.mov|{md5('two')}",
        f"ShowA/Day 1 – Interviews/take 01.wav|{md5('take')}",
        f"ShowA/Reel01/old_notes.txt|{md5('notes')}",
    ]) + "\n", encoding="utf-8")
    later = root / "delivery_v2.md5"
    later.write_text("\n".join([
        f"ShowA/Reel01/clip_0001.mov|{md5('one')}",
        f"ShowA/Reel01/clip_0002.mov|{md5('two, re-delivered')}",
        f"ShowA/Day_1_-_Interviews/take_01.wav|{md5('take')}",
        f"{HOSTILE}|{md5('new')}",
    ]) + "\n", encoding="utf-8")
    return earlier, later


def wait_until(test, timeout=20):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if test():
            return True
        time.sleep(0.2)
    return False


def drive(window, bridge, opened, earlier, later, out):
    js = window.evaluate_js
    r = {}
    time.sleep(2.5)
    window.run_js("document.querySelector('[data-screen=\"compare\"]').click()")
    time.sleep(0.5)
    r["compare_screen"] = js("!document.getElementById('screen-compare').hidden")
    r["button_disabled_at_first"] = js("document.getElementById('compareButton').disabled")
    window.run_js(f"window.app.dropped('earlier', {json.dumps(bridge.describe_manifest(str(earlier)))})")
    r["hint_after_one"] = js("document.getElementById('compareHint').textContent")
    window.run_js(f"window.app.dropped('later', {json.dumps(bridge.describe_manifest(str(later)))})")
    r["later_entries"] = js("document.getElementById('laterEntries').textContent")
    window.run_js("document.getElementById('compareButton').click()")
    r["results_shown"] = wait_until(lambda: js("!document.getElementById('cmpResults').hidden"))
    r["pill"] = js("document.getElementById('cmpPill').textContent")
    r["headline"] = js("document.getElementById('cmpHeadline').textContent")
    r["group_titles"] = js("Array.from(document.querySelectorAll('#cmpGroups h2')).map(e => e.textContent)")
    r["changed_rows"] = js("Array.from(document.querySelectorAll('[data-group=\"changed\"] tbody tr'))"
                           ".map(tr => Array.from(tr.children).map(td => td.textContent))")
    r["renamed_rows"] = js("Array.from(document.querySelectorAll('[data-group=\"renamed\"] tbody tr'))"
                           ".map(tr => Array.from(tr.children).map(td => td.textContent))")
    r["only_later_rows"] = js("Array.from(document.querySelectorAll('[data-group=\"only_later\"] tbody tr'))"
                              ".map(tr => tr.children[1].textContent)")
    r["unchanged"] = js("document.getElementById('cmpUnchanged').textContent")
    r["limits"] = js("document.getElementById('cmpLimits').textContent")
    r["images"] = js("document.querySelectorAll('#screen-compare img').length")
    r["title"] = js("document.title")

    window.run_js("{ const s = document.getElementById('cmpSearch'); s.value = 'clip_0001'; s.dispatchEvent(new Event('input')); }")
    wait_until(lambda: js("!document.getElementById('cmpSearchBox').hidden"), 10)
    r["search_rows"] = js("Array.from(document.querySelectorAll('#cmpSearchBox tbody tr'))"
                          ".map(tr => Array.from(tr.children).map(td => td.textContent))")
    window.run_js("{ const s = document.getElementById('cmpSearch'); s.value = 'no such file'; s.dispatchEvent(new Event('input')); }")
    wait_until(lambda: js("document.getElementById('cmpSearchCount').textContent.startsWith('No file')"), 10)
    r["search_none"] = js("document.getElementById('cmpSearchCount').textContent")

    window.run_js("document.getElementById('cmpShowFolder').click()")
    wait_until(lambda: bool(opened), 10)
    r["opened"] = [p.name for p in opened]
    window.run_js("document.getElementById('cmpAgain').click()")
    time.sleep(0.5)
    r["fresh_again"] = js("document.getElementById('cmpResults').hidden && !document.getElementById('earlierEmpty').hidden"
                          " && document.getElementById('compareButton').disabled")
    Path(out).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    window.destroy()


def main(out, workdir):
    root = Path(workdir)
    earlier, later = make_lists(root)
    opened = []
    bridge = Bridge(settings_file=root / "settings.json", secrets=SecretStore(backend=FakeKeyring()),
                    opener=opened.append)
    bridge.save_settings({"reports_dir": str(root / "reports")})
    window = create_window(bridge)

    def start(window, bridge):
        bind_drops(window, bridge)
        drive(window, bridge, opened, earlier, later, out)

    webview.start(start, (window, bridge), http_server=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
