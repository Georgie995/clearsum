"""Opens the ClearSum window: the pages in `web/`, the bridge, and drag-and-drop.

Drops are handled here because only Python learns a dropped item's real location
(pywebview adds it to the drop event); the page then just shows the result.
"""

import json
from pathlib import Path

import webview
from webview.dom import DOMEventHandler

from .bridge import Bridge

WEB = Path(__file__).parent / "web"


def create_window(bridge):
    window = webview.create_window("ClearSum", url=str(WEB / "index.html"), js_api=bridge,
                                   width=1280, height=880, min_size=(960, 640),
                                   background_color="#FBFAF7", text_select=True)
    bridge._choose = lambda kind: _pick(window, kind)
    return window


def bind_drops(window, bridge):
    for kind, selector in (("folder", "#folderCard"), ("manifest", "#manifestCard"),
                           ("earlier", "#earlierCard"), ("later", "#laterCard")):
        card = window.dom.get_element(selector)
        card.events.dragover += DOMEventHandler(_ignore, prevent_default=True, stop_propagation=True, debounce=500)
        card.events.drop += DOMEventHandler(_on_drop(window, bridge, kind), prevent_default=True, stop_propagation=True)
    # Anything dropped elsewhere is ignored, rather than the window trying to open it.
    window.dom.document.events.dragover += DOMEventHandler(_ignore, prevent_default=True, debounce=500)
    window.dom.document.events.drop += DOMEventHandler(_ignore, prevent_default=True)


def main():
    bridge = Bridge()
    window = create_window(bridge)
    webview.start(bind_drops, (window, bridge), http_server=True)


def _on_drop(window, bridge, kind):
    def handler(event):
        files = event.get("dataTransfer", {}).get("files", [])
        paths = [f["pywebviewFullPath"] for f in files if f.get("pywebviewFullPath")]
        if len(paths) == 1:
            info = bridge.describe_folder(paths[0]) if kind == "folder" else bridge.describe_manifest(paths[0])
        elif paths:
            info = {"ok": False, "error": "Add one item at a time."}
        else:
            info = {"ok": False, "error": "That couldn't be added. Try the Choose button instead."}
        # json.dumps keeps every character escaped, so a strange file name can't break out of the call.
        window.run_js(f"window.app.dropped({json.dumps(kind)}, {json.dumps(info)})")
    return handler


def _pick(window, kind):
    if kind == "folder":
        result = window.create_file_dialog(webview.FileDialog.FOLDER)
    elif kind == "manifest":
        result = window.create_file_dialog(
            webview.FileDialog.OPEN, file_types=("Checksum manifests (*.md5;*.sha256;*.txt)", "All files (*.*)"))
    else:
        result = window.create_file_dialog(webview.FileDialog.OPEN)
    return result[0] if result else None


def _ignore(event):
    pass
