"""ClearSum's own settings: where things live on this computer.

Never secrets: those are kept in Windows Credential Manager (secret_store.py). Unknown fields are
refused, so a secret can't end up in this file by accident.
"""

import json
import os
import tomllib
from pathlib import Path

FIELDS = ("reports_dir", "ops_hub_path", "ops_hub_config", "ai_triage_path", "ai_triage_python")


class SettingsError(Exception):
    def __init__(self, field, message):
        super().__init__(message)
        self.field = field  # so the Settings screen can point at the box that needs fixing


def default_settings_file():
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "ClearSum" / "settings.json"


def default_reports_dir():
    return str(Path.home() / "Documents" / "ClearSum Reports")


def load(path):
    path = Path(path)
    if not path.exists():
        return validate({"reports_dir": default_reports_dir()})
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        # Reported, never silently replaced: the person may want to fix or keep it.
        raise SettingsError(None, f"the settings file {path} can't be read ({error})") from error
    return validate(data)


def save(path, values):
    clean = validate(values)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(clean, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, path)  # all or nothing
    return clean


def validate(values):
    unknown = sorted(set(values) - set(FIELDS))
    if unknown:
        raise SettingsError(unknown[0], f"unknown setting: {unknown[0]}")
    clean = {key: (str(values.get(key) or "").strip() or None) for key in FIELDS}

    if not clean["reports_dir"]:
        raise SettingsError("reports_dir", "Choose a reports folder: every check's report is kept there.")
    _pair(clean, "ops_hub_path", "ops_hub_config", "delivery-ops-hub's folder and its settings file")
    _pair(clean, "ai_triage_path", "ai_triage_python", "ai-triage's folder and its Python")

    if clean["ops_hub_path"]:
        if not (Path(clean["ops_hub_path"]) / "delivery_ops_hub").is_dir():
            raise SettingsError("ops_hub_path", "delivery-ops-hub isn't in that folder.")
        if not _hub_reports_dir(clean["ops_hub_config"]):
            raise SettingsError("ops_hub_config", "That settings file has no reports_dir, so reports couldn't be found.")
    if clean["ai_triage_path"]:
        if not Path(clean["ai_triage_path"]).is_dir():
            raise SettingsError("ai_triage_path", "That ai-triage folder can't be found.")
        if not Path(clean["ai_triage_python"]).is_file():
            raise SettingsError("ai_triage_python", "That Python can't be found.")
    return clean


def reports_folder(settings):
    """Georgi's rule: with alerts set up, use delivery-ops-hub's reports folder so alerts, log and
    app always agree; otherwise the Reports folder from Settings."""
    if settings["ops_hub_path"]:
        return str(Path(_hub_reports_dir(settings["ops_hub_config"])))
    return settings["reports_dir"]


def _pair(clean, first, second, what):
    if bool(clean[first]) != bool(clean[second]):
        missing = second if clean[first] else first
        raise SettingsError(missing, f"Set both {what}, or neither.")


def _hub_reports_dir(config):
    try:
        return tomllib.loads(Path(config).read_text(encoding="utf-8")).get("reports_dir")
    except (OSError, ValueError):
        return None
