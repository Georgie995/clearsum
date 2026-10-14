"""A check running in the background, so the window never freezes while files are read.

The engine (delivery-desk) does the work; this keeps hold of it, reads manifest-doctor's progress
file for the progress bar, works out the time left, warns if reading seems stuck, collects messages,
and passes on Stop.
"""

import json
import threading
import time
from pathlib import Path

MAX_MESSAGES = 500


class CheckRun:
    def __init__(self, engine_call, progress_path, clock=time.monotonic, stall_seconds=600):
        self._engine_call = engine_call          # engine_call(output, stop) -> the engine's Outcome
        self._progress_path = Path(progress_path)
        self._clock = clock
        self._stall_seconds = stall_seconds      # from Settings; Georgi's job-watch rule is 10 minutes
        self._seen = None                        # the last reading progress seen, and when it changed
        self._seen_at = None
        self._stop = threading.Event()
        self._messages = []
        self._lock = threading.Lock()
        self._state = "idle"
        self._started = None
        self._ended = None
        self._outcome = None
        self._error = None

    @property
    def running(self):
        return self._state == "running"

    def start(self):
        self._state = "running"
        self._started = self._clock()
        threading.Thread(target=self._work, daemon=True).start()

    def stop(self):
        self._stop.set()

    def status(self):
        progress = self._read_progress() if self._state == "running" else {}
        now = self._ended if self._ended is not None else self._clock()
        elapsed = (now - self._started) if self._started is not None else 0
        with self._lock:
            messages = list(self._messages)
        return {"state": self._state, "progress": progress, "elapsed_seconds": round(elapsed),
                "eta_seconds": self._eta(progress, elapsed), "stalled": self._stalled(progress, now),
                "messages": messages, "outcome": self._outcome_view(), "error": self._error}

    def _work(self):
        state, outcome, error = "failed", None, None
        try:
            outcome = self._engine_call(self._output, self._stop)
            state = "stopped" if outcome.stopped else "finished"
        except Exception as problem:  # shown to the person in plain words, never a crash
            error = str(problem)
        finally:
            self._tidy()
            self._outcome, self._error, self._ended = outcome, error, self._clock()
            self._state = state  # last of all: the screen sees the end only once everything is tidy

    def _tidy(self):
        """Remove our own temporary progress file. On Windows it can't be removed at the instant the
        screen is reading it, so try again shortly; a leftover temp file is never worth an error."""
        for _ in range(20):
            try:
                self._progress_path.unlink(missing_ok=True)
                return
            except PermissionError:
                time.sleep(0.05)
            except OSError:
                return

    def _output(self, line):
        with self._lock:
            self._messages.append(line.rstrip("\n"))
            del self._messages[:-MAX_MESSAGES]

    def _read_progress(self):
        try:
            return json.loads(self._progress_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}  # not written yet, or caught mid-update: the next look will have it

    @staticmethod
    def _eta(progress, elapsed):
        """Time left from how fast data has been read so far. No guess before reading has properly begun."""
        done, total = progress.get("bytes_done") or 0, progress.get("bytes_total") or 0
        if progress.get("stage") != "hashing" or done <= 0 or total <= done or elapsed < 1:
            return None
        return round((total - done) / (done / elapsed))

    def _stalled(self, progress, now):
        """The stuck warning: nothing has moved for stall_seconds while files are being read.
        Any change counts as moving: more data read, another file done, or a new file started, so a
        huge file that is still being read is never called stuck. While the folder is being listed
        there's no progress signal at all, so slow and stuck look the same: no warning then."""
        if self._state != "running":
            return None
        if progress:                                    # an unreadable moment changes nothing
            if progress.get("stage") != "hashing":
                self._seen = self._seen_at = None
                return None
            moved = (progress.get("bytes_done"), progress.get("files_done"), progress.get("current_file"))
            if moved != self._seen:
                self._seen, self._seen_at = moved, now
        if self._seen_at is None or now - self._seen_at < self._stall_seconds:
            return None
        return {"file": self._seen[2], "minutes": int((now - self._seen_at) // 60)}

    def _outcome_view(self):
        o = self._outcome
        if o is None:
            return None
        return {"code": o.code, "result": o.result, "report_id": o.report_folder.name if o.report_folder else None,
                "has_note": o.note is not None, "stopped": o.stopped}
