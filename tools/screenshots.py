r"""Take the README's screenshots from the real app, driven through its screens (a developer tool,
not part of the app). Synthetic deliveries only, in a neutral folder, so no real paths appear.

    .venv\Scripts\python tools\screenshots.py D:\Deliveries

Uses Windows' own PrintWindow to photograph the window; writes PNGs to docs\screenshots.
"""

import ctypes
import json
import struct
import sys
import time
import zlib
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import webview  # noqa: E402

from check_driver import make_deliveries, run_check, wait_for  # noqa: E402
from clearsum.app import bind_drops, create_window  # noqa: E402
from clearsum.bridge import Bridge  # noqa: E402
from clearsum.secret_store import SecretStore  # noqa: E402
from window_driver import FakeKeyring  # noqa: E402

OUT = ROOT / "docs" / "screenshots"
ANSWERS = ["Delivered on 3 October. Re-delivered on 9 October, when the newer clip_0004.mov replaced the first one.",
           "clip_0004.mov exists on two tapes with different content, and set1.md5 lists both versions.",
           "Re-deliver the first version under a different name, so both versions exist side by side.",
           "Restore it from tape 1, rename it clip_0004_v1.mov, upload it, and send a corrected manifest."]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long), ("biYPelsPerMeter", ctypes.c_long),
                ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


def capture(path):
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    hwnd = user32.FindWindowW(None, "ClearSum")
    rect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    width, height = rect.right, rect.bottom
    window_dc = user32.GetDC(hwnd)
    dc = gdi32.CreateCompatibleDC(window_dc)
    bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
    gdi32.SelectObject(dc, bitmap)
    user32.PrintWindow(hwnd, dc, 0x1 | 0x2)          # client area only, full web content
    header = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
    pixels = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(dc, bitmap, 0, height, pixels, ctypes.byref(header), 0)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(dc)
    user32.ReleaseDC(hwnd, window_dc)
    bgra = pixels.raw
    rgb = bytearray(width * height * 3)
    rgb[0::3], rgb[1::3], rgb[2::3] = bgra[2::4], bgra[1::4], bgra[0::4]
    rows = b"".join(b"\x00" + bytes(rgb[y * width * 3:(y + 1) * width * 3]) for y in range(height))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))
    path.write_bytes(png)


def drive(window, bridge, root):
    js = window.evaluate_js
    time.sleep(3)
    window.run_js(f"window.app.dropped('folder', {json.dumps(bridge.describe_folder(str(root / 'show-a-ep01')))})")
    window.run_js(f"window.app.dropped('manifest', {json.dumps(bridge.describe_manifest(str(root / 'set1.md5')))})")
    time.sleep(1)
    capture(OUT / "1-start.png")

    window.run_js("document.getElementById('checkButton').click()")
    wait_for(window, "results")
    time.sleep(1)
    capture(OUT / "2-problems-found.png")

    window.run_js("document.getElementById('startNote').click()")
    wait_for(window, "note", timeout=20)
    for text in ANSWERS[:2]:
        window.run_js(f"document.getElementById('qText').value = {json.dumps(text)}; document.getElementById('qNext').click();")
        time.sleep(0.8)
    capture(OUT / "3-incident-note.png")

    for text in ANSWERS[2:]:
        window.run_js(f"document.getElementById('qText').value = {json.dumps(text)}; document.getElementById('qNext').click();")
        time.sleep(0.8)
    window.run_js("document.getElementById('qLine').value = 'clip_0004 overwritten on re-delivery';"
                  "document.getElementById('makeEmail').click();")
    wait_for(window, "email", timeout=20)
    time.sleep(1)
    capture(OUT / "4-email-ready.png")

    window.run_js("document.getElementById('emAgain').click()")
    time.sleep(0.5)
    run_check(window, bridge, root / "show-a-ep02", root / "set2.md5")
    wait_for(window, "allclear")
    time.sleep(1)
    capture(OUT / "5-all-clear.png")

    window.run_js("document.querySelector('[data-screen=\"earlier\"]').click()")
    time.sleep(1.5)
    capture(OUT / "6-earlier-checks.png")
    window.destroy()


def main(base):
    root = make_deliveries(base)
    OUT.mkdir(parents=True, exist_ok=True)
    bridge = Bridge(settings_file=root / "settings.json", secrets=SecretStore(backend=FakeKeyring()))
    bridge.save_settings({"reports_dir": str(root / "Reports")})
    window = create_window(bridge)

    def start(window, bridge):
        bind_drops(window, bridge)
        drive(window, bridge, root)

    webview.start(start, (window, bridge), http_server=True)


if __name__ == "__main__":
    main(sys.argv[1])
