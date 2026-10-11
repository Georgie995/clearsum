# PyInstaller build recipe for the double-click Windows app.
#   .venv\Scripts\python -m PyInstaller packaging\delivery-desk.spec --noconfirm
# Output: dist\Delivery Desk\Delivery Desk.exe (a folder app: start-up is quicker than one big .exe).

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, copy_metadata

ROOT = Path(SPECPATH).parent            # delivery-desk-app
PROJECTS = ROOT.parent
ENGINE = {                               # bundled so the app needs nothing else installed
    "delivery_desk": PROJECTS / "delivery-desk",
    "manifest_doctor": PROJECTS / "delivery-verify",
    "delivery_ops_hub": PROJECTS / "delivery-ops-hub",
}
for folder in [ROOT, *ENGINE.values()]:
    sys.path.insert(0, str(folder))      # so the engine's own imports are found and bundled

hidden = ["delivery_desk_app"] + collect_submodules("delivery_desk_app")
for package in ENGINE:
    hidden += [package] + collect_submodules(package)
hidden += collect_submodules("keyring.backends")   # Credential Manager is found through these

datas = [(str(ROOT / "delivery_desk_app" / "web"), "delivery_desk_app/web")]
# The engine's source also travels as plain folders: the engine checks those folders exist.
datas += [(str(parent / package), f"engine/{package}") for package, parent in ENGINE.items()]
datas += copy_metadata("keyring")                  # keyring discovers its backends from this
datas += [(str(ROOT / "LICENSE"), "."), (str(ROOT / "packaging" / "THIRD-PARTY-NOTICES.txt"), ".")]

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT), *[str(p) for p in ENGINE.values()]],
    datas=datas,
    hiddenimports=hidden,
    excludes=["tkinter", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Delivery Desk", console=False,
          upx=False)                     # UPX compression often upsets antivirus tools; left off
coll = COLLECT(exe, a.binaries, a.datas, name="Delivery Desk", upx=False)
