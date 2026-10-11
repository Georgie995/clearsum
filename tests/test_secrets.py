"""Module 2: secrets live in Windows Credential Manager (a stand-in here), never anywhere else."""

import pytest

from clearsum.secret_store import SERVICE, SecretError


def test_a_saved_secret_is_reported_as_saved_but_its_value_is_never_given_back(secrets):
    secrets.save("webhook_secret", "  hook-123  ")
    assert secrets.status() == {"webhook_secret": True, "ai_key": False}
    assert "hook-123" not in repr(secrets.status())


def test_secrets_are_stored_under_the_app_name_and_trimmed(secrets, keyring_box):
    secrets.save("ai_key", " key-456\n")
    assert keyring_box.saved == {(SERVICE, "ai_key"): "key-456"}


def test_secrets_for_a_run_use_the_names_the_tools_expect(secrets):
    secrets.save("webhook_secret", "hook-123")
    secrets.save("ai_key", "key-456")
    assert secrets.for_run() == {"OPS_HUB_WEBHOOK_SECRET": "hook-123", "ANTHROPIC_API_KEY": "key-456"}


def test_removing_works_and_removing_twice_is_harmless(secrets):
    secrets.save("webhook_secret", "hook-123")
    secrets.remove("webhook_secret")
    secrets.remove("webhook_secret")
    assert secrets.status()["webhook_secret"] is False and secrets.for_run() == {}


@pytest.mark.parametrize("name, value", [("webhook_secret", "   "), ("password", "x")])
def test_empty_values_and_unknown_names_are_refused(secrets, name, value):
    with pytest.raises(SecretError):
        secrets.save(name, value)


def test_secrets_are_kept_under_the_apps_name_in_credential_manager():
    assert SERVICE == "ClearSum"
