"""Opens the real app window, drives it like a person would, records what it shows, and closes it.
Run by test_window.py in its own process (a window must own its program's main thread)."""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import webview  # noqa: E402

from delivery_desk_app.app import bind_drops, create_window  # noqa: E402
from delivery_desk_app.bridge import Bridge  # noqa: E402
from delivery_desk_app.secret_store import SecretStore  # noqa: E402

HOSTILE = '<img src=x onerror="document.title=\'INJECTED\'">clip.mov'
SECRET = "hook-TEST-ONLY-123"


class FakeKeyring:
    def __init__(self):
        self.saved = {}

    def get_password(self, service, name):
        return self.saved.get((service, name))

    def set_password(self, service, name, value):
        self.saved[(service, name)] = value

    def delete_password(self, service, name):
        del self.saved[(service, name)]


def drive(window, bridge, keyring, out):
    js = window.evaluate_js
    r = {}
    time.sleep(2.5)
    r["heading"] = js("document.querySelector('#screen-start h1').textContent")
    r["check_disabled_at_start"] = js("document.getElementById('checkButton').disabled")
    r["has_security_policy"] = js("!!document.querySelector('meta[http-equiv=\"Content-Security-Policy\"]')")

    hostile = {"ok": True, "name": HOSTILE, "path": "D:\\Deliveries\\" + HOSTILE, "files": 1204}
    window.run_js(f"window.app.dropped('folder', {json.dumps(hostile)})")
    window.run_js("window.app.dropped('manifest', " + json.dumps({"ok": False, "error": "a folder, not a manifest"}) + ")")
    time.sleep(1)
    r["folder_name_shown"] = js("document.getElementById('folderName').textContent")
    r["images_in_folder_card"] = js("document.querySelectorAll('#folderCard img').length")
    r["title_after_hostile"] = js("document.title")
    r["files_text"] = js("document.getElementById('folderFiles').textContent")
    r["manifest_error"] = js("document.getElementById('manifestError').textContent")
    good = {"ok": True, "name": "set1.md5", "path": "D:\\Deliveries\\set1.md5", "entries": 1205}
    window.run_js(f"window.app.dropped('manifest', {json.dumps(good)})")
    time.sleep(0.5)
    r["check_enabled_when_both"] = not js("document.getElementById('checkButton').disabled")

    window.run_js("document.querySelector('[data-screen=\"settings\"]').click()")
    time.sleep(1.5)
    r["alerts_status"] = js("document.getElementById('alertsStatus').textContent")
    window.run_js("document.getElementById('modeAdvanced').click();"
                  "document.getElementById('f-ops_hub_path').value = 'D:/somewhere';"
                  "document.getElementById('saveSettings').click();")
    time.sleep(1.5)
    r["settings_error"] = js("document.getElementById('e-ops_hub_config').textContent")
    window.run_js(f"document.getElementById('s-webhook_secret').value = {json.dumps(SECRET)};"
                  "document.querySelector('[data-save-secret=\"webhook_secret\"]').click();")
    time.sleep(1.5)
    r["secret_box_empty"] = js("document.getElementById('s-webhook_secret').value") == ""
    r["secret_saved_shown"] = not js("document.getElementById('webhook_secret-saved').hidden")
    r["secret_in_page"] = SECRET in js("document.documentElement.outerHTML + document.body.innerText")
    r["secret_in_store"] = keyring.saved.get(("Delivery Desk", "webhook_secret")) == SECRET
    Path(out).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    window.destroy()


def main(out, settings_file):
    keyring = FakeKeyring()
    bridge = Bridge(settings_file=settings_file, secrets=SecretStore(backend=keyring))
    window = create_window(bridge)

    def start(window, bridge):
        bind_drops(window, bridge)
        drive(window, bridge, keyring, out)

    webview.start(start, (window, bridge), http_server=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
