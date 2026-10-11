"""Module 7: the double-click Windows app.

The launcher's "tool mode", the third-party notices, and (when it has been built) the packaged
app's own self-test.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from clearsum import paths

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "packaging" / "launcher.py"
BUILT = ROOT / "dist" / "ClearSum" / "ClearSum.exe"
sys.path.insert(0, str(ROOT / "packaging"))

from make_notices import notices_text, runtime_distributions  # noqa: E402


def launch(*args, env=None):
    return subprocess.run([sys.executable, str(LAUNCHER), *args], capture_output=True, text=True, timeout=60, env=env)


def test_tool_mode_refuses_anything_that_isnt_one_of_the_apps_tools():
    result = launch("-m", "os")
    assert result.returncode != 0 and "isn't one of the app's tools" in result.stderr


@pytest.mark.skipif(not (paths.MANIFEST_DOCTOR / "manifest_doctor").is_dir(), reason="manifest-doctor not next to the app")
def test_tool_mode_behaves_like_python_dash_m(tmp_path):
    env = dict(os.environ, PYTHONPATH=str(paths.MANIFEST_DOCTOR))
    result = launch("-m", "manifest_doctor", "check", "--help", env=env)
    assert result.returncode == 0 and "--manifest" in result.stdout


def test_every_bundled_library_has_its_licence_in_the_notices():
    text = notices_text()
    names = runtime_distributions()
    assert {"pywebview", "keyring", "pythonnet"} <= {n.lower() for n in names}
    for name in names:
        assert f"=== {name} " in text, name
        entry = text.split(f"=== {name} ")[1].split("\n=== ")[0]
        assert len(entry) > 200, f"{name}: only a licence name, not its text"   # MIT/BSD need the notice itself
    assert "Microsoft Corporation" in text and "PYTHON SOFTWARE FOUNDATION LICENSE" in text.upper()


@pytest.mark.skipif(not BUILT.exists(), reason="the app hasn't been built (packaging/build.py)")
def test_the_built_app_passes_its_own_self_test(tmp_path):
    out = tmp_path / "selftest.json"
    subprocess.run([str(BUILT), "--self-test", str(out)], timeout=180, check=True)
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["frozen"] is True and result["web_files"] is True
    assert result["keyring_backend"] == "WinVaultKeyring"           # Windows Credential Manager was found
    assert result["heading"] == "Check a delivery"
    assert (result["check_state"], result["tool_messages_seen"], result["note_written"]) == ("finished", True, True)
    assert result["headline"] == "1 file didn't arrive as expected."


@pytest.mark.skipif(not BUILT.exists(), reason="the app hasn't been built (packaging/build.py)")
def test_the_built_app_carries_its_licence_and_the_notices():
    folder = BUILT.parent / "_internal"
    assert (folder / "LICENSE").is_file()
    assert "=== pywebview " in (folder / "THIRD-PARTY-NOTICES.txt").read_text(encoding="utf-8")


@pytest.mark.skipif(not BUILT.exists(), reason="the app hasn't been built (packaging/build.py)")
def test_the_built_app_holds_no_trace_of_the_computer_it_was_built_on():
    sys.path.insert(0, str(ROOT / "packaging"))
    from build import local_traces
    assert local_traces(BUILT.parent) == []
