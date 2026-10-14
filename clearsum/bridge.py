"""The bridge: the only things the app's pages can ask Python to do.

Every public method here can be called from the page, so the list is kept short and each one
checks what it's given. Nothing here deletes, moves or changes a delivery. Secret values go in,
never out: the page only ever learns whether a secret is saved.
"""

import os
import tempfile
import uuid
from pathlib import Path

from . import comparisons, history, notes, paths, results, settings_store
from .checking import CheckRun
from .results import REPORT_ID
from .secret_store import SecretError, SecretStore
from .settings_store import SettingsError


class Bridge:
    def __init__(self, settings_file=None, secrets=None, choose=None, engine=None, opener=None, clipboard=None):
        self._settings_file = Path(settings_file or settings_store.default_settings_file())
        self._secrets = secrets or SecretStore()
        self._choose = choose  # set by app.py: opens the Windows picker; returns a path or None
        self._engine = engine  # delivery-desk's engine; loaded on first use unless a test gives one
        self._opener = opener or _open_in_explorer      # a report folder, or a mailto: draft
        self._clipboard = clipboard or _copy_to_clipboard
        self._run = None

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

    # --- Checking and results ---------------------------------------------------------------------------

    def start_check(self, folder, manifest):
        if self._run is not None and self._run.running:
            return {"ok": False, "error": "A check is already running. Wait for it to finish, or stop it."}
        for described in (self.describe_folder(folder), self.describe_manifest(manifest)):
            if not described["ok"]:
                return described
        try:
            values = settings_store.load(self._settings_file)
        except SettingsError as error:
            return {"ok": False, "error": f"{error} Open Settings to fix it."}
        engine = self._engine or paths.load_engine()
        settings = _engine_settings(values)
        secrets = self._secrets.for_run()
        # The progress file lives in the system's temporary folder: never inside the delivery.
        progress = Path(tempfile.gettempdir()) / f"clearsum-progress-{uuid.uuid4().hex}.json"
        args = ["--manifest", str(manifest), "--progress-file", str(progress)]
        Path(settings["reports_dir"]).mkdir(parents=True, exist_ok=True)

        def call(output, stop):
            return engine.check(settings, folder, args, secrets=secrets, output=output, stop=stop)

        self._run = CheckRun(call, progress, stall_seconds=values["stall_minutes"] * 60)
        self._alerts = bool(settings["ops_hub_path"])
        self._run.start()
        return {"ok": True}

    def check_status(self):
        if self._run is None:
            return {"state": "idle"}
        return {**self._run.status(), "alerts": self._alerts}  # the screen words the alert line from this

    def stop_check(self):
        if self._run is not None:
            self._run.stop()
        return {"ok": True}

    def get_result(self, report_id):
        folder = self._report_folder(report_id)
        if folder is None:
            return {"ok": False, "error": "That report can't be found."}
        return results.summarise(folder)

    def show_report_folder(self, report_id):
        folder = self._report_folder(report_id)
        if folder is None:
            return {"ok": False, "error": "That report folder can't be found."}
        self._opener(folder)
        return {"ok": True}

    # --- Compare lists: two versions of a delivery's checksum list -----------------------------------------

    def compare_lists(self, earlier, later):
        for described in (self.describe_manifest(earlier), self.describe_manifest(later)):
            if not described["ok"]:
                return described
        try:
            reports = Path(settings_store.reports_folder(settings_store.load(self._settings_file)))
        except SettingsError as error:
            return {"ok": False, "error": f"{error} Open Settings to fix it."}
        comparer = paths.load_comparer()
        try:
            comparison = comparer.compare_lists(earlier, later)
        except comparer.ManifestError as error:
            return {"ok": False, "error": f"The lists couldn't be compared: {error}"}
        return comparisons.summarise(comparer.write_comparison(comparison, reports))

    def search_comparison(self, compare_id, text):
        folder = self._comparison_folder(compare_id)
        if folder is None:
            return {"ok": False, "error": "That comparison can't be found."}
        return {"ok": True, **comparisons.search(folder, text)}

    def show_comparison_folder(self, compare_id):
        folder = self._comparison_folder(compare_id)
        if folder is None:
            return {"ok": False, "error": "That comparison folder can't be found."}
        self._opener(folder)
        return {"ok": True}

    # --- Earlier checks --------------------------------------------------------------------------------

    def list_checks(self):
        try:
            folder = settings_store.reports_folder(settings_store.load(self._settings_file))
        except SettingsError as error:
            return {"ok": False, "error": str(error), "checks": [], "total": 0}
        return history.list_checks(folder)

    # --- Incident note and manager email -------------------------------------------------------------

    def get_note(self, report_id):
        folder = self._note_folder(report_id)
        return notes.note_view(folder) if folder else _no_note()

    def save_answer(self, report_id, heading, text, expected):
        folder = self._note_folder(report_id)
        if folder is None:
            return _no_note()
        note_errors = paths.load_engine("note").NoteError
        try:
            return notes.save_answer(folder, str(heading), str(text or ""), expected)
        except notes.NoteConflict as conflict:
            return {"ok": False, "conflict": True, "error": str(conflict), "note": notes.note_view(folder)}
        except note_errors as error:
            return {"ok": False, "conflict": False, "error": str(error)}
        except OSError as error:
            return {"ok": False, "conflict": False, "error": f"The note couldn't be saved: {error.strerror}"}

    def make_email(self, report_id):
        folder = self._note_folder(report_id)
        return notes.make_email(folder) if folder else _no_note()

    def copy_email(self, report_id):
        folder = self._note_folder(report_id)
        text = notes.latest_email(folder) if folder else None
        if text is None:
            return {"ok": False, "error": "Make the email first."}
        try:
            self._clipboard(text)
        except OSError as error:
            return {"ok": False, "error": str(error)}
        return {"ok": True}

    def open_email(self, report_id):
        """A new draft in the default mail app. ClearSum never sends anything itself."""
        folder = self._note_folder(report_id)
        text = notes.latest_email(folder) if folder else None
        if text is None:
            return {"ok": False, "error": "Make the email first."}
        url, body_included = notes.mailto_url(*notes.split_email(text))
        if not body_included:
            self._clipboard(text)  # too long for the link: it's on the clipboard to paste instead
        self._opener(url)
        return {"ok": True, "body_included": body_included}

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

    def _report_folder(self, report_id):
        """Only a real report folder, directly inside the reports folder in use: a name from the page
        can never reach anywhere else on the computer."""
        if not isinstance(report_id, str) or not REPORT_ID.fullmatch(report_id):
            return None
        try:
            reports = Path(settings_store.reports_folder(settings_store.load(self._settings_file)))
        except SettingsError:
            return None
        folder = reports / report_id
        return folder if (folder / "report.json").is_file() else None

    def _comparison_folder(self, compare_id):
        """Only a real comparison folder, directly inside the reports folder in use."""
        if not isinstance(compare_id, str) or not comparisons.COMPARE_ID.fullmatch(compare_id):
            return None
        try:
            reports = Path(settings_store.reports_folder(settings_store.load(self._settings_file)))
        except SettingsError:
            return None
        folder = reports / compare_id
        return folder if (folder / "comparison.json").is_file() else None

    def _note_folder(self, report_id):
        folder = self._report_folder(report_id)
        return folder if folder is not None and (folder / "incident-note.md").is_file() else None

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


def _engine_settings(values):
    """What delivery-desk's engine needs: through delivery-ops-hub when alerts are set up,
    otherwise manifest-doctor directly into the app's Reports folder."""
    common = {"ai_triage_path": values["ai_triage_path"], "ai_triage_python": values["ai_triage_python"]}
    if values["ops_hub_path"]:
        return {"ops_hub_path": values["ops_hub_path"], "ops_hub_config": values["ops_hub_config"],
                "reports_dir": settings_store.reports_folder(values), **common}
    return {"ops_hub_path": None, "ops_hub_config": None, "manifest_doctor_path": str(paths.MANIFEST_DOCTOR),
            "reports_dir": values["reports_dir"], **common}


def _open_in_explorer(target):
    # Windows: a checked report folder opens in File Explorer; a mailto: link opens a new draft.
    os.startfile(target)


def _copy_to_clipboard(text):
    from .clipboard import copy_text
    copy_text(text)


def _no_note():
    return {"ok": False, "error": "That incident note can't be found."}


def _count_files(folder):
    # Reads names only, never file contents. Unreadable sub-folders are skipped, not fatal.
    return sum(len(files) for _, _, files in os.walk(folder, onerror=lambda error: None))


def _count_entries(manifest):
    try:
        with open(manifest, encoding="utf-8", errors="replace") as handle:
            return sum(1 for line in handle if line.strip() and not line.lstrip().startswith(("#", ";")))
    except OSError:
        return 0
