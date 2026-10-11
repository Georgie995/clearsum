"""The bridge: the only things the app's pages can ask Python to do.

Every public method here can be called from the page, so the list is kept short and each one
checks what it's given. Nothing here deletes, moves or changes a delivery. Secret values go in,
never out: the page only ever learns whether a secret is saved.
"""

import os
from pathlib import Path

from . import settings_store
from .secret_store import SecretError, SecretStore
from .settings_store import SettingsError


class Bridge:
    def __init__(self, settings_file=None, secrets=None, choose=None):
        self._settings_file = Path(settings_file or settings_store.default_settings_file())
        self._secrets = secrets or SecretStore()
        self._choose = choose  # set by app.py: opens the Windows picker; returns a path or None

    # --- Start screen ---------------------------------------------------------------------------------

    def choose_folder(self):
        path = self._choose("folder") if self._choose else None
        return self.describe_folder(path) if path else None

    def choose_manifest(self):
        path = self._choose("manifest") if self._choose else None
        return self.describe_manifest(path) if path else None

    def describe_folder(self, path):
        target = Path(str(path))
        if not target.exists():
            return {"ok": False, "error": f"{target.name or path} can't be found. Was it moved or renamed?"}
        if not target.is_dir():
            return {"ok": False, "error": f"{target.name} is a file, not a folder. Add the delivery folder here."}
        return {"ok": True, "name": target.name, "path": str(target), "files": _count_files(target)}

    def describe_manifest(self, path):
        target = Path(str(path))
        if not target.exists():
            return {"ok": False, "error": f"{target.name or path} can't be found. Was it moved or renamed?"}
        if target.is_dir():
            return {"ok": False, "error": f"{target.name} is a folder, not a manifest file. "
                                          "Add the checksum manifest here, such as an .md5 file."}
        return {"ok": True, "name": target.name, "path": str(target), "entries": _count_entries(target)}

    # --- Settings ---------------------------------------------------------------------------------------

    def choose_path(self, kind):
        """For the Browse buttons in Settings: kind is "folder" or "file"."""
        if kind not in ("folder", "file") or not self._choose:
            return None
        return self._choose(kind)

    def get_settings(self):
        try:
            values = settings_store.load(self._settings_file)
            warning = None
        except SettingsError as error:
            values = settings_store.validate({"reports_dir": settings_store.default_reports_dir()})
            warning = f"{error} Showing the defaults; saving will replace that file."
        return self._view(values, warning)

    def save_settings(self, values):
        try:
            clean = settings_store.save(self._settings_file, dict(values))
        except SettingsError as error:
            return {"ok": False, "field": error.field, "error": str(error)}
        except OSError as error:
            return {"ok": False, "field": None, "error": f"Settings couldn't be saved: {error.strerror}"}
        return self._view(clean, None)

    def save_secret(self, name, value):
        try:
            self._secrets.save(name, value)
        except SecretError as error:
            return {"ok": False, "field": name, "error": str(error)}
        return self.get_settings()

    def remove_secret(self, name):
        try:
            self._secrets.remove(name)
        except SecretError as error:
            return {"ok": False, "field": name, "error": str(error)}
        return self.get_settings()

    # --- Helpers (not callable from the page) -----------------------------------------------------------

    def _view(self, values, warning):
        secrets = self._secrets.status()
        if not values["ops_hub_path"]:
            alerts = "not_set_up"
        else:
            alerts = "set_up" if secrets["webhook_secret"] else "needs_secret"
        if not values["ai_triage_python"]:
            ai = "not_set_up"
        else:
            ai = "set_up" if secrets["ai_key"] else "no_key"
        return {"ok": True, "values": values, "secrets": secrets, "status": {"alerts": alerts, "ai": ai},
                "reports_in_use": settings_store.reports_folder(values), "warning": warning}


def _count_files(folder):
    # Reads names only, never file contents. Unreadable sub-folders are skipped, not fatal.
    return sum(len(files) for _, _, files in os.walk(folder, onerror=lambda error: None))


def _count_entries(manifest):
    try:
        with open(manifest, encoding="utf-8", errors="replace") as handle:
            return sum(1 for line in handle if line.strip() and not line.lstrip().startswith(("#", ";")))
    except OSError:
        return 0
