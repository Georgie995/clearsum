"""Shared test helpers. Synthetic data only; the real Windows Credential Manager is never touched."""

import pytest

from delivery_desk_app.secret_store import SecretStore


class FakeKeyring:
    """Stands in for Windows Credential Manager: a dictionary in memory."""
    def __init__(self):
        self.saved = {}

    def get_password(self, service, name):
        return self.saved.get((service, name))

    def set_password(self, service, name, value):
        self.saved[(service, name)] = value

    def delete_password(self, service, name):
        del self.saved[(service, name)]


@pytest.fixture
def keyring_box():
    return FakeKeyring()


@pytest.fixture
def secrets(keyring_box):
    return SecretStore(backend=keyring_box)


@pytest.fixture
def hub(tmp_path):
    """Just enough of a delivery-ops-hub folder and its settings file."""
    (tmp_path / "hub" / "delivery_ops_hub").mkdir(parents=True)
    config = tmp_path / "hub" / "ops-hub.toml"
    config.write_text(f'reports_dir = "{(tmp_path / "hub-reports").as_posix()}"\n', encoding="utf-8")
    return tmp_path / "hub", config


@pytest.fixture
def triage(tmp_path):
    """Just enough of an ai-triage folder and its Python."""
    folder = tmp_path / "ai-triage"
    (folder / ".venv" / "Scripts").mkdir(parents=True)
    python = folder / ".venv" / "Scripts" / "python.exe"
    python.write_text("stand-in", encoding="utf-8")
    return folder, python
