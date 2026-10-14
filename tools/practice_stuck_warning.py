r"""See the stuck warning for yourself (a developer tool, not part of the app).

Opens the real ClearSum window with practice settings in a temporary folder, so your own settings
are never touched, and the warning time set to 1 minute. A pretend check of made-up files reads for
about 15 seconds, then gets "stuck" for two and a half minutes, then reads again until you press
Stop. Nothing real is checked; nothing is changed anywhere.

    .venv\Scripts\python tools\practice_stuck_warning.py
"""

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import webview  # noqa: E402

from clearsum.app import bind_drops, create_window  # noqa: E402
from clearsum.bridge import Bridge  # noqa: E402
from clearsum.secret_store import SecretStore  # noqa: E402
from window_driver import FakeKeyring  # noqa: E402

FILES = [f"ShowA/Reel0{reel}/clip_00{n:02d}.mov" for reel in (1, 2, 3) for n in range(40, 45)]
READ_FIRST, STUCK_FOR = 15, 150          # seconds: reads, then gets stuck on whichever file it's on


class PracticeEngine:
    """Pretends to check: moves for a while, stops moving, then moves again until Stop."""

    def check(self, settings, tree, doctor_args, secrets=None, output=None, stop=None):
        progress = Path(doctor_args[doctor_args.index("--progress-file") + 1])
        total = len(FILES) * 1000
        state = {"stage": "hashing", "files_done": 0, "files_total": len(FILES), "bytes_done": 0,
                 "bytes_total": total, "current_file": FILES[0]}
        start = time.monotonic()
        while not stop.wait(1):
            elapsed = time.monotonic() - start
            stuck = READ_FIRST <= elapsed < READ_FIRST + STUCK_FOR
            if not stuck and state["bytes_done"] < total - 100:
                state["bytes_done"] += 100
                state["files_done"] = state["bytes_done"] // 1000
                state["current_file"] = FILES[min(state["files_done"], len(FILES) - 1)]
            progress.write_text(json.dumps(state), encoding="utf-8")
        return SimpleNamespace(code=130, result=None, report_folder=None, note=None, stopped=True)


def main():
    work = Path(tempfile.mkdtemp(prefix="clearsum-practice-"))
    (work / "delivery").mkdir()
    (work / "delivery" / "made-up.mov").write_bytes(b"practice")
    (work / "practice.md5").write_text("0" * 32 + "  made-up.mov\n", encoding="utf-8")
    bridge = Bridge(settings_file=work / "settings.json", secrets=SecretStore(backend=FakeKeyring()),
                    engine=PracticeEngine())
    bridge.save_settings({"reports_dir": str(work / "reports"), "stall_minutes": "1"})
    print(__doc__)
    print("Press Check. After about 15 seconds the pretend check gets stuck; the warning appears a")
    print("minute later, and clears by itself about a minute and a half after that. Press Stop any time.")
    window = create_window(bridge)

    def start(window, bridge):
        bind_drops(window, bridge)
        time.sleep(2)
        window.run_js(f"window.app.dropped('folder', {json.dumps(bridge.describe_folder(str(work / 'delivery')))})")
        window.run_js(f"window.app.dropped('manifest', {json.dumps(bridge.describe_manifest(str(work / 'practice.md5')))})")

    try:
        webview.start(start, (window, bridge), http_server=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)           # the practice folder goes when the window closes


if __name__ == "__main__":
    main()
