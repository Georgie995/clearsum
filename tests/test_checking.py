"""Module 3: a check runs in the background, reports progress, and can be stopped."""

import json
import threading
import time
from types import SimpleNamespace

from clearsum.checking import CheckRun


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


# --- The "stuck" warning: nothing read for a while (Georgi's job-watch rule: 10 minutes) -------------

def running(tmp_path, stall_seconds=600):
    progress = tmp_path / "p.json"
    clock = SimpleNamespace(now=0.0)
    run = CheckRun(lambda output, stop: outcome(), progress, clock=lambda: clock.now, stall_seconds=stall_seconds)
    run._started, run._state = 0.0, "running"
    return run, progress, clock


def reading(progress, **state):
    progress.write_text(json.dumps({"stage": "hashing", **state}), encoding="utf-8")


def test_after_ten_minutes_with_nothing_read_a_warning_names_the_file(tmp_path):
    run, progress, clock = running(tmp_path)
    reading(progress, bytes_done=500, files_done=3, current_file="Reel03/clip_0042.mov")
    assert run.status()["stalled"] is None
    clock.now = 599
    assert run.status()["stalled"] is None
    clock.now = 600
    assert run.status()["stalled"] == {"file": "Reel03/clip_0042.mov", "minutes": 10}
    clock.now = 750
    assert run.status()["stalled"]["minutes"] == 12          # keeps counting while it's stuck


def test_the_warning_clears_as_soon_as_reading_resumes(tmp_path):
    run, progress, clock = running(tmp_path)
    reading(progress, bytes_done=500, files_done=3, current_file="Reel03/clip_0042.mov")
    run.status()
    clock.now = 700
    assert run.status()["stalled"] is not None
    reading(progress, bytes_done=600, files_done=3, current_file="Reel03/clip_0042.mov")
    assert run.status()["stalled"] is None


def test_a_big_file_that_is_still_being_read_is_never_called_stuck(tmp_path):
    run, progress, clock = running(tmp_path)
    for minute in range(0, 60, 5):                           # an hour on one file, data still moving
        clock.now = minute * 60
        reading(progress, bytes_done=minute * 10**9, files_done=0, current_file="Reel01/huge.mxf")
        assert run.status()["stalled"] is None


def test_moving_on_to_another_file_counts_as_progress(tmp_path):
    # e.g. empty files: no data is read, but files are still being dealt with
    run, progress, clock = running(tmp_path)
    reading(progress, bytes_done=0, files_done=1, current_file="a.txt")
    run.status()
    clock.now = 700
    reading(progress, bytes_done=0, files_done=2, current_file="b.txt")
    assert run.status()["stalled"] is None


def test_no_warning_while_the_folder_is_still_being_listed(tmp_path):
    # Listing gives no progress signal, so slow and stuck look the same there: no warning.
    run, progress, clock = running(tmp_path)
    progress.write_text(json.dumps({"stage": "preparing"}), encoding="utf-8")
    run.status()
    clock.now = 3600
    assert run.status()["stalled"] is None


def test_a_moment_when_the_progress_file_cant_be_read_doesnt_restart_the_count(tmp_path):
    run, progress, clock = running(tmp_path)
    reading(progress, bytes_done=500, files_done=3, current_file="x.mov")
    run.status()
    clock.now = 300
    progress.write_text("{ half", encoding="utf-8")
    run.status()
    clock.now = 600
    reading(progress, bytes_done=500, files_done=3, current_file="x.mov")
    assert run.status()["stalled"] is not None


def test_the_time_limit_comes_from_the_setting(tmp_path):
    run, progress, clock = running(tmp_path, stall_seconds=60)
    reading(progress, bytes_done=1, files_done=0, current_file="x.mov")
    run.status()
    clock.now = 60
    assert run.status()["stalled"] == {"file": "x.mov", "minutes": 1}


def test_a_check_that_has_ended_is_never_stuck(tmp_path):
    run, progress, clock = running(tmp_path)
    reading(progress, bytes_done=500, files_done=3, current_file="x.mov")
    run.status()
    clock.now = 900
    run._state = "finished"
    assert run.status()["stalled"] is None
