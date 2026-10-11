"""Write THIRD-PARTY-NOTICES.txt: the licence of everything the packaged app carries.

Works out the libraries from what pywebview and keyring actually need on Windows (and what those
need), so a new dependency can't be missed. Their licences (MIT, BSD and others) ask for their
notices to travel with the app.
"""

import sys
from importlib.metadata import distribution
from pathlib import Path

from packaging.requirements import Requirement

HERE = Path(__file__).parent
TOP_LEVEL = ["pywebview", "keyring"]          # the app's own dependencies (pyproject.toml)
ENVIRONMENT = {"sys_platform": "win32", "platform_system": "Windows", "os_name": "nt", "extra": ""}


def runtime_distributions():
    seen, queue = {}, list(TOP_LEVEL)
    while queue:
        name = queue.pop()
        dist = distribution(name)
        if dist.metadata["Name"].lower() in {n.lower() for n in seen}:
            continue
        seen[dist.metadata["Name"]] = dist
        for line in dist.requires or []:
            requirement = Requirement(line)
            if requirement.marker is None or requirement.marker.evaluate(ENVIRONMENT):
                queue.append(requirement.name)
    return sorted(seen, key=str.lower)


def notices_text():
    parts = ["Delivery Desk bundles the following third-party software. Each is listed with its licence.\n",
             "The bundled fonts' licences (SIL Open Font License 1.1) are in clearsum/web/fonts.\n"]
    python_licence = Path(sys.base_prefix) / "LICENSE.txt"
    parts.append(f"\n=== Python {sys.version.split()[0]} ===\n" + python_licence.read_text(encoding="utf-8", errors="replace"))
    for name in runtime_distributions():
        dist = distribution(name)
        texts = [f.read_text(encoding="utf-8", errors="replace") for f in _licence_files(dist)]
        kept_here = HERE / "licenses" / f"{name}-LICENSE.txt"   # for a package that ships no licence file
        if not texts and kept_here.is_file():
            texts = [kept_here.read_text(encoding="utf-8")]
        if not texts:
            texts = [dist.metadata.get("License-Expression") or dist.metadata.get("License") or "(licence not stated)"]
        parts.append(f"\n=== {name} {dist.version} ===\n" + "\n".join(texts))
    parts.append("\n=== Microsoft WebView2 SDK ===\n" + (HERE / "licenses" / "WebView2-SDK-LICENSE.txt").read_text(encoding="utf-8"))
    parts.append("\n=== PyInstaller bootloader ===\nThe app was packaged with PyInstaller (GPL-2.0-or-later with the PyInstaller "
                 "bootloader exception, which allows packaging programs under any licence).\n")
    return "".join(parts)


def _licence_files(dist):
    wanted = ("license", "licence", "copying", "notice")
    files = [f for f in dist.files or [] if any(w in f.name.lower() for w in wanted)]
    return [Path(dist.locate_file(f)) for f in files if Path(dist.locate_file(f)).is_file()]


if __name__ == "__main__":
    (HERE / "THIRD-PARTY-NOTICES.txt").write_text(notices_text(), encoding="utf-8")
    print("THIRD-PARTY-NOTICES.txt written:", ", ".join(runtime_distributions()))
