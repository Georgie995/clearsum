r"""Build the double-click Windows app in one go:

    .venv\Scripts\python packaging\build.py

1. write THIRD-PARTY-NOTICES.txt from the libraries actually bundled;
2. build dist\ClearSum\ with PyInstaller (packaging\clearsum.spec);
3. run the packaged app's own self-test; stop if anything is wrong;
4. zip the folder as dist\ClearSum-<version>-windows.zip, ready to attach to a release.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "dist" / "ClearSum"


def local_traces(folder):
    """Files in the build that mention the folders of the computer it was built on (for example a
    compiled file that recorded where it was compiled). A published app must carry none."""
    places = {str(ROOT.parent), str(Path.home())}
    needles = set()
    for place in places:
        for text in (place, place.replace("\\", "/")):
            needles |= {text.encode("utf-8"), text.encode("utf-16-le")}
    return sorted(str(p.relative_to(folder)) for p in Path(folder).rglob("*")
                  if p.is_file() and any(n in p.read_bytes() for n in needles))


def main():
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    subprocess.run([sys.executable, str(ROOT / "packaging" / "make_notices.py")], check=True)
    subprocess.run([sys.executable, "-m", "PyInstaller", str(ROOT / "packaging" / "clearsum.spec"),
                    "--noconfirm", "--log-level", "WARN"], check=True, cwd=ROOT)

    out = Path(tempfile.mkdtemp()) / "selftest.json"
    subprocess.run([str(APP / "ClearSum.exe"), "--self-test", str(out)], check=True, timeout=180)
    result = json.loads(out.read_text(encoding="utf-8"))
    print(json.dumps(result, indent=1))
    healthy = (result["frozen"] and result["web_files"] and result["keyring_backend"] == "WinVaultKeyring"
               and result["check_state"] == "finished" and result["tool_messages_seen"] and result["note_written"])
    if not healthy:
        sys.exit("The packaged app failed its self-test: not zipped.")
    traces = local_traces(APP)
    if traces:
        sys.exit("The build mentions this computer's folders, so it was not zipped: " + ", ".join(traces[:5]))

    archive = shutil.make_archive(str(ROOT / "dist" / f"ClearSum-{version}-windows"), "zip",
                                  root_dir=APP.parent, base_dir=APP.name)
    print(f"Built and checked: {archive} ({Path(archive).stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
