"""Where the engine and the checker live.

While the app is being built, they are the sibling project folders next to this one. In the
packaged app they travel inside it (packaging/clearsum.spec copies them to `engine/`).
This is the one place that knows the difference.
"""

import importlib
import sys
from pathlib import Path

if getattr(sys, "frozen", False):   # the packaged app (PyInstaller)
    PROJECTS = None
    DELIVERY_DESK = MANIFEST_DOCTOR = Path(sys._MEIPASS) / "engine"
else:
    PROJECTS = Path(__file__).resolve().parents[2]
    DELIVERY_DESK = PROJECTS / "delivery-desk"
    MANIFEST_DOCTOR = PROJECTS / "delivery-verify"   # manifest-doctor's local folder


def load_engine(part="desk"):
    """One part of delivery-desk's engine: desk (checking), note, manager_email or files."""
    if not (DELIVERY_DESK / "delivery_desk").is_dir():
        raise RuntimeError(f"delivery-desk's engine wasn't found at {DELIVERY_DESK}")
    if str(DELIVERY_DESK) not in sys.path:
        sys.path.insert(0, str(DELIVERY_DESK))
    return importlib.import_module(f"delivery_desk.{part}")
