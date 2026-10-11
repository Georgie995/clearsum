"""Module 3: a check runs in the background, reports progress, and can be stopped."""

import json
import threading
import time
from types import SimpleNamespace

from delivery_desk_app.checking import CheckRun


def outcome(code=1, result="PROBLEMS FOUND", folder="report-2026", note=True, stopped=False):
    from pathlib import Path
    return SimpleNamespace(code=code, result=result, report_folder=Path("R") / folder if folder else None,
                           note=Path("R") / folder / "incident-note.md" if note else None, stopped=stopped)


def wait_until(run, states, timeout=5):
    end = time.monotonic() + timeout
    while run.status()["state"] not in states:
        assert time.monotonic() < end, run.status()
        time.sleep(0.02)
    return run.status()


def test_progress_is_read_while_it_runs_and_the_outcome_arrives_at_the_end(tmp_path):
    progress = tmp_path / "progress.json"
    gate = threading.Event()

    def engine(output, stop):
        progress.write_text(json.dumps({"stage": "hashing", "files_done": 312, "files_total": 1204, "bytes_done": 50,
                                        "bytes_total": 200, "current_file": "ShowA/clip_0312.mov"}), encoding="utf-8")
        output("RESULT: PROBLEMS FOUND\n")
        gate.wait(5)
        return outcome()

    run = CheckRun(engine, progress)
    run.start()
    time.sleep(0.3)
    status = run.status()
    assert status["state"] == "running"
    assert (status["progress"]["files_done"], status["progress"]["current_file"]) == (312, "ShowA/clip_0312.mov")
    gate.set()
    done = wait_until(run, {"finished"})
    assert done["outcome"] == {"code": 1, "result": "PROBLEMS FOUND", "report_id": "report-2026", "has_note": True,
                               "stopped": False}
    assert done["messages"] == ["RESULT: PROBLEMS FOUND"]


def test_time_left_comes_from_how_fast_data_has_been_read(tmp_path):
    progress = tmp_path / "progress.json"
    clock = SimpleNamespace(now=0.0)
    run = CheckRun(lambda output, stop: outcome(), progress, clock=lambda: clock.now)
    run._started = 0.0
    run._state = "running"
    progress.write_text(json.dumps({"stage": "hashing", "bytes_done": 100, "bytes_total": 400}), encoding="utf-8")
    clock.now = 10.0
    assert run.status()["eta_seconds"] == 30          # 100 bytes in 10 s, 300 to go


def test_no_time_left_is_guessed_before_reading_has_properly_started(tmp_path):
    progress = tmp_path / "progress.json"
    run = CheckRun(lambda output, stop: outcome(), progress, clock=lambda: 0.5)
    run._started, run._state = 0.0, "running"
    progress.write_text(json.dumps({"stage": "preparing"}), encoding="utf-8")
    assert run.status()["eta_seconds"] is None


def test_stop_reaches_the_engine_and_the_check_ends_as_stopped(tmp_path):
    seen = {}

    def engine(output, stop):
        seen["stop"] = stop
        stop.wait(5)
        return outcome(code=130, result=None, folder=None, note=False, stopped=True)

    run = CheckRun(engine, tmp_path / "p.json")
    run.start()
    time.sleep(0.2)
    run.stop()
    assert wait_until(run, {"stopped"})["outcome"]["stopped"] is True
    assert seen["stop"].is_set()


def test_a_problem_starting_the_check_is_reported_in_plain_words(tmp_path):
    def engine(output, stop):
        raise ValueError("--out is set by delivery-desk")

    run = CheckRun(engine, tmp_path / "p.json")
    run.start()
    status = wait_until(run, {"failed"})
    assert "--out is set by delivery-desk" in status["error"]


def test_a_half_written_or_missing_progress_file_never_breaks_the_status(tmp_path):
    progress = tmp_path / "p.json"
    run = CheckRun(lambda output, stop: outcome(), progress)
    run._started, run._state = 0.0, "running"
    assert run.status()["progress"] == {}
    progress.write_text("{ half", encoding="utf-8")
    assert run.status()["progress"] == {}


def test_the_progress_file_is_tidied_away_when_the_check_ends(tmp_path):
    progress = tmp_path / "p.json"

    def engine(output, stop):
        progress.write_text("{}", encoding="utf-8")
        return outcome()

    run = CheckRun(engine, progress)
    run.start()
    wait_until(run, {"finished"})
    assert not progress.exists()


def test_tidying_up_survives_the_screen_reading_the_progress_file_at_that_moment(tmp_path, monkeypatch):
    from pathlib import Path
    progress = tmp_path / "p.json"
    real_unlink = Path.unlink
    attempts = {"n": 0}

    def busy_once(self, missing_ok=False):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise PermissionError(32, "being used by another process")   # Windows, mid-read
        return real_unlink(self, missing_ok=missing_ok)

    def engine(output, stop):
        progress.write_text("{}", encoding="utf-8")
        return outcome()

    monkeypatch.setattr(Path, "unlink", busy_once)
    run = CheckRun(engine, progress)
    run.start()
    assert wait_until(run, {"finished"})["state"] == "finished"
    time.sleep(0.5)
    assert not progress.exists() and attempts["n"] >= 2
