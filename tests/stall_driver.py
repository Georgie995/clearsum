"""Opens the real app, starts a check whose stand-in engine gets "stuck", and records the stuck
warning appearing, clearing when reading resumes, and Stop still working. The time limit is cut
to 3 seconds here only, so the test doesn't wait 10 minutes. Run by test_window_stall.py in its
own process. Synthetic files only; no real engine, no network."""

import json
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import webview  # noqa: E402

import clearsum.bridge as bridge_module  # noqa: E402
from clearsum.app import bind_drops, create_window  # noqa: E402
from clearsum.checking import CheckRun  # noqa: E402
from clearsum.secret_store import SecretStore  # noqa: E402
from check_driver import run_check, wait_for  # noqa: E402
from window_driver import FakeKeyring  # noqa: E402

STUCK_ON = "ShowA/<img src=x onerror=\"document.title='INJECTED'\">.mov"   # a name that looks like code


class StuckEngine:
    """Reads a little, then stops moving until told to resume, then waits for Stop."""
    def __init__(self):
        self.resume = threading.Event()

    def check(self, settings, tree, doctor_args, secrets=None, output=None, stop=None):
        progress = Path(doctor_args[doctor_args.index("--progress-file") + 1])

        def write(done):
            progress.write_text(json.dumps({"stage": "hashing", "files_done": 2, "files_total": 5, "bytes_done": done,
                                            "bytes_total": 5000, "current_file": STUCK_ON}), encoding="utf-8")
        write(1000)
        self.resume.wait(60)
        write(2000)                                    # reading moves again
        stop.wait(60)
        return SimpleNamespace(code=130, result=None, report_folder=None, note=None, stopped=True)


def visible(window):
    return window.evaluate_js("!document.getElementById('stallWarning').hidden")


def wait_until(test, timeout):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if test():
            return True
        time.sleep(0.1)
    return False


def drive(window, bridge, engine, root, out):
    js = window.evaluate_js
    r = {}
    time.sleep(2.5)
    run_check(window, bridge, root / "delivery", root / "set1.md5")
    r["checking_screen"] = wait_for(window, "checking", timeout=15)
    r["hidden_at_first"] = not visible(window)
    r["appeared"] = wait_until(lambda: visible(window), 15)
    r["text"] = js("document.getElementById('stallWarning').textContent")
    r["file_in_mono"] = js("Array.from(document.querySelectorAll('#stallWarning .mono')).map(e => e.textContent)")
    r["images_in_warning"] = js("document.querySelectorAll('#stallWarning img').length")
    r["title"] = js("document.title")
    engine.resume.set()
    r["cleared_when_reading_resumed"] = wait_until(lambda: not visible(window), 2.5)
    window.run_js("document.getElementById('stopButton').click()")
    r["stopped_back_to_start"] = wait_for(window, "start", timeout=15)
    r["hidden_after_stop"] = not visible(window)
    Path(out).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    window.destroy()


def main(out, workdir):
    root = Path(workdir)
    (root / "delivery" / "ShowA").mkdir(parents=True)
    (root / "delivery" / "ShowA" / "clip_0001.mov").write_bytes(b"synthetic")
    (root / "set1.md5").write_text("0" * 32 + "  ShowA/clip_0001.mov\n", encoding="utf-8")
    # The 3-second limit, for this test only: every check the app starts gets it.
    bridge_module.CheckRun = lambda call, progress, stall_seconds: CheckRun(call, progress, stall_seconds=3)
    engine = StuckEngine()
    bridge = bridge_module.Bridge(settings_file=root / "settings.json", secrets=SecretStore(backend=FakeKeyring()),
                                  engine=engine)
    bridge.save_settings({"reports_dir": str(root / "reports")})
    window = create_window(bridge)

    def start(window, bridge):
        bind_drops(window, bridge)
        drive(window, bridge, engine, root, out)

    webview.start(start, (window, bridge), http_server=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
