"""Secrets live in Windows Credential Manager, the password store built into Windows.

They are read only when a tool runs, and handed to that one tool (see delivery-desk's engine).
Nothing here ever returns a secret's value to the pages: only whether it is saved.
"""

SERVICE = "Delivery Desk"
# The app's name for each secret, and the name the tool that needs it expects.
NAMES = {"webhook_secret": "OPS_HUB_WEBHOOK_SECRET", "ai_key": "ANTHROPIC_API_KEY"}


class SecretError(Exception):
    """A plain-language reason a secret wasn't saved."""


class SecretStore:
    def __init__(self, backend=None):
        if backend is None:
            import keyring  # only the real app touches Credential Manager; tests pass a stand-in
            backend = keyring
        self._backend = backend

    def save(self, name, value):
        self._known(name)
        value = (value or "").strip()
        if not value:
            raise SecretError("Paste the secret first: the box is empty.")
        self._backend.set_password(SERVICE, name, value)

    def remove(self, name):
        self._known(name)
        if self._backend.get_password(SERVICE, name) is not None:
            self._backend.delete_password(SERVICE, name)

    def status(self):
        return {name: self._backend.get_password(SERVICE, name) is not None for name in NAMES}

    def for_run(self):
        """Only for starting a check: {name the tool expects: value}, for the secrets that are saved."""
        values = {env: self._backend.get_password(SERVICE, name) for name, env in NAMES.items()}
        return {env: value for env, value in values.items() if value}

    @staticmethod
    def _known(name):
        if name not in NAMES:
            raise SecretError(f"Unknown secret: {name}")
