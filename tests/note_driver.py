"""Opens the real app, runs a REAL check on a synthetic delivery with problems, then writes the
incident note and makes the email entirely through the screens. Clipboard and mail app are
stand-ins. Records what's shown, then closes. Run by test_window_note.py in its own process."""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import webview  # noqa: E402

from check_driver import make_deliveries, run_check, wait_for  # noqa: E402
from delivery_desk_app.app import bind_drops, create_window  # noqa: E402
from delivery_desk_app.bridge import Bridge  # noqa: E402
from delivery_desk_app.secret_store import SecretStore  # noqa: E402
from window_driver import FakeKeyring  # noqa: E402

ANSWERS = [
    "Delivered on 3 October. Re-delivered on 9 October.",
    "clip_0004.mov exists on two tapes. <img src=x onerror=\"document.title='INJECTED'\">",
    "Re-deliver the first version under a different name.",
    "Restore it from tape 1, rename it clip_0004_v1.mov, and upload it.",
]
SUBJECT = "clip_0004 overwritten on re-delivery"


def type_answer(window, text, field="qText"):
    window.run_js(f"document.getElementById('{field}').value = {json.dumps(text)}")


def drive(window, bridge, root, copied, opened, out):
    js = window.evaluate_js
    r = {}
    time.sleep(2.5)
    run_check(window, bridge, root / "show-a-ep01", root / "set1.md5")
    wait_for(window, "results")
    window.run_js("document.getElementById('startNote').click()")
    r["note_screen"] = wait_for(window, "note", timeout=20)
    r["first_question"] = js("document.getElementById('qTitle').textContent")
    r["still_empty_at_start"] = js("document.getElementById('stillEmpty').textContent")
    r["private_causes"] = js("document.getElementById('privCauses').textContent")

    for i, text in enumerate(ANSWERS):
        type_answer(window, text)
        window.run_js("document.getElementById('qNext').click()")
        time.sleep(0.6)
    r["subject_question_uses_one_line"] = js("!document.getElementById('qLine').hidden && document.getElementById('qText').hidden")
    type_answer(window, SUBJECT, "qLine")

    # Reword "The problem", as a person might for their manager.
    window.run_js("const p = document.getElementById('fc-problem'); p.value = 'Two errors, both on clip_0004.mov.';"
                  "p.dispatchEvent(new Event('change'));")
    time.sleep(0.6)
    window.run_js("document.getElementById('makeEmail').click()")
    r["email_screen"] = wait_for(window, "email", timeout=20)
    r["subject"] = js("document.getElementById('emSubject').textContent")
    r["parts"] = js("Array.from(document.querySelectorAll('#emBody > div')).map(d => d.innerText)")
    r["images_in_email"] = js("document.querySelectorAll('#screen-email img').length")
    r["title_after_email"] = js("document.title")
    r["file"] = js("document.getElementById('emFile').textContent")

    window.run_js("document.getElementById('copyEmail').click()")
    time.sleep(0.6)
    r["copied"] = copied[:]
    r["copy_label"] = js("document.getElementById('copyEmail').textContent")
    window.run_js("document.getElementById('openEmail').click()")
    time.sleep(0.6)
    r["opened"] = [u for u in opened if str(u).startswith("mailto:")]
    time.sleep(0.6)
    r["recent_after_email"] = js("Array.from(document.querySelectorAll('#recentList .recent-item')).map(b => b.innerText.trim())")

    # Edit my answers, while the note has meanwhile been changed in a text editor.
    note_file = next(root.glob("reports/report-*/incident-note.md"))
    text = note_file.read_text(encoding="utf-8")
    note_file.write_text(text.replace(ANSWERS[0], "Changed in Notepad."), encoding="utf-8")
    window.run_js("document.getElementById('editAnswers').click()")
    time.sleep(1)
    window.run_js("document.querySelector('#answerList button').click()")   # back to question 1
    time.sleep(0.8)
    r["q1_after_notepad"] = js("document.getElementById('qText').value")

    # The dangerous case: the screen is open, the note changes in Notepad, THEN the person types and moves on.
    text = note_file.read_text(encoding="utf-8")
    note_file.write_text(text.replace(ANSWERS[2], "Fix typed in Notepad."), encoding="utf-8")
    window.run_js("document.querySelectorAll('#answerList button')[2].click()")      # question 3, as last shown
    time.sleep(0.8)
    type_answer(window, "Fix typed in the app.")
    window.run_js("document.getElementById('qNext').click()")
    time.sleep(1)
    r["conflict_message"] = js("document.getElementById('toast').textContent")
    r["q3_after_conflict"] = js("document.getElementById('qText').value")
    saved = note_file.read_text(encoding="utf-8")
    r["file_kept_notepad_fix"] = "Fix typed in Notepad." in saved and "Fix typed in the app." not in saved
    r["note_files"] = sorted(p.name for p in note_file.parent.iterdir())
    Path(out).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    window.destroy()


def main(out, workdir):
    root = make_deliveries(workdir)
    copied, opened = [], []
    bridge = Bridge(settings_file=root / "settings.json", secrets=SecretStore(backend=FakeKeyring()),
                    clipboard=copied.append, opener=opened.append)
    bridge.save_settings({"reports_dir": str(root / "reports")})
    window = create_window(bridge)

    def start(window, bridge):
        bind_drops(window, bridge)
        drive(window, bridge, root, copied, opened, out)

    webview.start(start, (window, bridge), http_server=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
