"""Opens the real app and runs REAL checks through delivery-desk and manifest-doctor on synthetic
deliveries: one with problems, one clean, one that can't be checked. Records what each screen
shows, then closes. Run by test_window_check.py in its own process. No alerts, no AI, no network."""

import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import webview  # noqa: E402

from clearsum.app import bind_drops, create_window  # noqa: E402
from clearsum.bridge import Bridge  # noqa: E402
from clearsum.secret_store import SecretStore  # noqa: E402
from window_driver import FakeKeyring  # noqa: E402


def make_deliveries(root):
    root = Path(root)
    files = {f"ShowA/Reel01/clip_000{i}.mov": f"synthetic frames {i}".encode() for i in range(1, 5)}
    for name in ("show-a-ep01", "show-a-ep02"):
        for rel, data in files.items():
            (root / name / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / name / rel).write_bytes(data)
    lines = [f"{hashlib.md5(d).hexdigest()}  {r}" for r, d in files.items()]
    (root / "set2.md5").write_text("\n".join(lines) + "\n", encoding="utf-8")                  # clean
    old = hashlib.md5(b"synthetic frames 4, first version").hexdigest()
    # A manifest can list any name, even one Windows wouldn't allow on disk: it becomes a "missing" row.
    hostile = "0" * 32 + "  ShowA/<img src=x onerror=\"document.title='INJECTED'\">.mov"
    (root / "set1.md5").write_text("\n".join(lines[:3] + [f"{old}  ShowA/Reel01/clip_0004.mov"] + lines[3:] + [hostile])
                                   + "\n", encoding="utf-8")                  # listed twice, plus a missing file
    (root / "empty.md5").write_text("", encoding="utf-8")                                       # can't be checked
    return root


def wait_for(window, screen, timeout=90):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if window.evaluate_js(f"!document.getElementById('screen-{screen}').hidden"):
            return True
        time.sleep(0.3)
    return False


def run_check(window, bridge, folder, manifest):
    window.run_js(f"window.app.dropped('folder', {json.dumps(bridge.describe_folder(str(folder)))})")
    window.run_js(f"window.app.dropped('manifest', {json.dumps(bridge.describe_manifest(str(manifest)))})")
    time.sleep(0.5)
    window.run_js("document.getElementById('checkButton').click()")


def drive(window, bridge, root, out):
    js = window.evaluate_js
    r = {}
    temp = Path(tempfile.gettempdir())                     # where progress files live during a check
    progress_before = set(temp.glob("clearsum-progress-*"))
    time.sleep(2.5)

    run_check(window, bridge, root / "show-a-ep01", root / "set1.md5")
    r["problems_screen"] = wait_for(window, "results")
    r["pill"] = js("document.getElementById('rsPill').textContent")
    r["headline"] = js("document.getElementById('results-title').textContent")
    r["errors"] = js("document.getElementById('rsErrors').textContent")
    r["cause_titles"] = js("Array.from(document.querySelectorAll('.cause-title')).map(e => e.textContent)")
    r["cause_files"] = js("Array.from(document.querySelectorAll('.cause-files li')).map(e => e.textContent)")
    r["rows"] = js("document.querySelectorAll('#rsRows tr').length")
    r["hostile_row_text"] = js("Array.from(document.querySelectorAll('#rsRows .file')).map(e => e.textContent)"
                               ".filter(t => t.includes('onerror'))")
    r["images_in_results"] = js("document.querySelectorAll('#screen-results img').length")
    r["title_after_results"] = js("document.title")
    r["start_note_shown"] = not js("document.getElementById('startNote').hidden")
    r["alert_line_hidden"] = js("document.getElementById('rsAlert').hidden")
    r["tools_said"] = js("document.getElementById('rsOutput').textContent")
    window.run_js("document.querySelector('[data-filter=\"INFO\"]').click()")
    time.sleep(0.3)
    r["info_rows"] = js("document.querySelectorAll('#rsRows tr').length")
    r["empty_note_shown"] = not js("document.getElementById('rsEmpty').hidden")
    r["rs_proves_shown"] = not js("document.getElementById('rsProves').hidden")
    r["rs_proved"] = js("document.getElementById('rsProved').textContent")
    r["rs_not_checked"] = js("Array.from(document.querySelectorAll('#rsNotChecked li')).map(e => e.textContent)")
    r["rs_not_checked_shown"] = not js("document.getElementById('rsNotCheckedBlock').hidden")
    r["rs_cant_tell"] = js("document.getElementById('rsCantTell').textContent")

    window.run_js("document.querySelector('#screen-results [data-again]').click()")
    time.sleep(0.5)
    r["back_to_start_empty"] = js("!document.getElementById('folderEmpty').hidden && !document.getElementById('manifestEmpty').hidden")
    run_check(window, bridge, root / "show-a-ep02", root / "set2.md5")
    r["allclear_screen"] = wait_for(window, "allclear")
    r["allclear_headline"] = js("document.getElementById('allclear-title').textContent")
    r["checked_values"] = js("Array.from(document.querySelectorAll('#acChecked .value')).map(e => e.textContent)")
    r["ac_proves_shown"] = not js("document.getElementById('acProves').hidden")
    r["ac_proved"] = js("document.getElementById('acProved').textContent")
    r["ac_not_checked_hidden"] = js("document.getElementById('acNotCheckedBlock').hidden")

    window.run_js("document.querySelector('#screen-allclear [data-again]').click()")
    time.sleep(0.5)
    run_check(window, bridge, root / "show-a-ep02", root / "empty.md5")
    r["notchecked_screen"] = wait_for(window, "notchecked")
    r["nc_reason"] = js("document.getElementById('ncReason').textContent")
    r["nc_output"] = js("document.getElementById('ncOutput').textContent")
    # Earlier checks and Recent, after the three checks above, plus an old synthetic report whose
    # delivery name looks like code (as one made on a Linux machine could be).
    r["reports"] = sorted(p.name for p in (root / "reports").iterdir() if p.is_dir())
    old = root / "reports" / "report-2000-01-01_000000"
    old.mkdir()
    (old / "report.json").write_text(json.dumps({"header": {
        "result": "CLEAN", "tree": "/mnt/deliveries/<img src=x onerror=\"document.title='INJECTED'\">",
        "run_at": "2000-01-01T00:00:00+00:00", "counts": {}, "manifests": [{"path": "old.md5", "entries": 1}]},
        "causes": [], "findings": []}), encoding="utf-8")
    window.run_js("document.querySelector('[data-screen=\"earlier\"]').click()")
    time.sleep(1.5)
    r["earlier_rows"] = js("Array.from(document.querySelectorAll('#ecRows tr'))"
                           ".map(tr => Array.from(tr.children).map(td => td.innerText.trim()))")
    r["recent"] = js("Array.from(document.querySelectorAll('#recentList .recent-item')).map(b => b.innerText.trim())")
    r["images_in_earlier_or_recent"] = js("document.querySelectorAll('#screen-earlier img, #recentList img').length")
    r["title_after_earlier"] = js("document.title")
    window.run_js("const s = document.getElementById('ecSearch'); s.value = 'ep01'; s.dispatchEvent(new Event('input'));")
    time.sleep(0.4)
    r["search_rows"] = js("document.querySelectorAll('#ecRows tr').length")
    window.run_js("document.querySelector('#ecRows .open-check').click()")
    r["reopened"] = wait_for(window, "results", timeout=15)
    r["reopened_headline"] = js("document.getElementById('results-title').textContent")
    r["reopened_note_button"] = js("document.getElementById('startNote').textContent")
    r["reopened_details_hidden"] = js("document.getElementById('rsDetails').hidden")
    # A report from before "what this check proves" existed: the panel simply isn't shown.
    window.run_js("document.querySelector('[data-screen=\"earlier\"]').click()")
    time.sleep(1)
    window.run_js("const t = document.getElementById('ecSearch'); t.value = 'old.md5'; t.dispatchEvent(new Event('input'));")
    time.sleep(0.4)
    window.run_js("document.querySelector('#ecRows .open-check').click()")
    r["old_report_opened"] = wait_for(window, "allclear", timeout=15)
    r["old_report_proves_hidden"] = js("document.getElementById('acProves').hidden")
    time.sleep(1)
    r["leftover_progress_files"] = sorted(p.name for p in set(temp.glob("clearsum-progress-*")) - progress_before)
    Path(out).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    window.destroy()


def main(out, workdir):
    root = make_deliveries(workdir)
    bridge = Bridge(settings_file=root / "settings.json", secrets=SecretStore(backend=FakeKeyring()))
    bridge.save_settings({"reports_dir": str(root / "reports")})
    window = create_window(bridge)

    def start(window, bridge):
        bind_drops(window, bridge)
        drive(window, bridge, root, out)

    webview.start(start, (window, bridge), http_server=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
