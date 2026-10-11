"""A self-test for the packaged app: `ClearSum.exe --self-test result.json`.

Opens the window for a few seconds and checks the page and fonts, runs a real check of a tiny
made-up delivery (through "tool mode"), and checks Windows Credential Manager is reachable,
without saving anything there. Writes what it found to the given file, then closes.
"""

import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path

import webview

from .app import WEB, bind_drops, create_window
from .bridge import Bridge
from .secret_store import SecretStore


class _MemoryKeyring:
    """The self-test never touches the real Credential Manager's contents."""
    def __init__(self):
        self.saved = {}

    def get_password(self, service, name):
        return self.saved.get((service, name))

    def set_password(self, service, name, value):
        self.saved[(service, name)] = value

    def delete_password(self, service, name):
        del self.saved[(service, name)]


def run(out):
    work = Path(tempfile.mkdtemp(prefix="clearsum-selftest-"))
    tree = work / "show-a-ep01"
    files = {"ShowA/clip_0001.mov": b"frames one", "ShowA/clip_0002.mov": b"frames two"}
    for rel, data in files.items():
        (tree / rel).parent.mkdir(parents=True, exist_ok=True)
        (tree / rel).write_bytes(data)
    (tree / "ShowA/clip_0002.mov").write_bytes(b"frames two, changed")
    manifest = work / "set1.md5"
    manifest.write_text("".join(f"{hashlib.md5(d).hexdigest()}  {r}\n" for r, d in files.items()), encoding="utf-8")

    bridge = Bridge(settings_file=work / "settings.json", secrets=SecretStore(backend=_MemoryKeyring()))
    bridge.save_settings({"reports_dir": str(work / "reports")})
    window = create_window(bridge)

    def checks(window, bridge):
        bind_drops(window, bridge)
        result = {"frozen": bool(getattr(sys, "frozen", False)), "executable": Path(sys.executable).name}
        try:
            import keyring
            result["keyring_backend"] = type(keyring.get_keyring()).__name__
        except Exception as error:  # reported, never hidden
            result["keyring_backend"] = f"error: {error}"
        result["web_files"] = all((WEB / name).is_file() for name in
                                  ("index.html", "app.css", "app.js", "fonts/Newsreader-Variable.ttf"))
        time.sleep(2.5)
        result["heading"] = window.evaluate_js("document.querySelector('#screen-start h1').textContent")
        result["fonts_loaded"] = sorted(set(window.evaluate_js(
            "Array.from(document.fonts).filter(f => f.status === 'loaded').map(f => f.family.replace(/\"/g, ''))")))
        started = bridge.start_check(str(tree), str(manifest))
        result["check_started"] = started
        status = bridge.check_status()
        end = time.monotonic() + 90
        while status.get("state") == "running" and time.monotonic() < end:
            time.sleep(0.3)
            status = bridge.check_status()
        result["check_state"] = status.get("state")
        result["check_error"] = status.get("error")
        result["tool_messages_seen"] = any("PROBLEMS FOUND" in line for line in status.get("messages", []))
        outcome = status.get("outcome") or {}
        result["headline"] = bridge.get_result(outcome["report_id"]).get("headline") if outcome.get("report_id") else None
        result["note_written"] = outcome.get("has_note")
        Path(out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        window.destroy()

    webview.start(checks, (window, bridge), http_server=True)
