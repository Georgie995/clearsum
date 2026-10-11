"""Where the engine and the checker live.

While the app is being built, they are the sibling project folders next to this one. The packaged
app (the last module) will carry them inside; that change is made here, in one place.
"""

import importlib
import sys
from pathlib import Path

PROJECTS = Path(__file__).resolve().parents[2]
DELIVERY_DESK = PROJECTS / "delivery-desk"
MANIFEST_DOCTOR = PROJECTS / "delivery-verify"   # manifest-doctor's local folder


def load_engine():
    if not (DELIVERY_DESK / "delivery_desk").is_dir():
        raise RuntimeError(f"delivery-desk's engine wasn't found at {DELIVERY_DESK}")
    if str(DELIVERY_DESK) not in sys.path:
        sys.path.insert(0, str(DELIVERY_DESK))
    return importlib.import_module("delivery_desk.desk")
