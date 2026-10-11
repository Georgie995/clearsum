"""The incident note and the manager email, done with delivery-desk's own tested code.

The note stays the single record: every answer is written straight into incident-note.md, and
only if that section still says what the screen last showed, so nothing typed elsewhere is lost.
"""

import re
from pathlib import Path
from urllib.parse import quote

from . import paths

# The prompts from Georgi's prototype, one question at a time.
QUESTIONS = [
    {"heading": "When it happened", "help": "When the problem actually happened, not when the check ran."},
    {"heading": "How it happened", "help": "The confirmed cause, in your words, once you’ve investigated."},
    {"heading": "How we intend to fix it",
     "help": "What will be done. For example: re-deliver the newer file under a different name."},
    {"heading": "Most plausible way to do it",
     "help": "How best to do it. For example: copy it from tape 2, rename it with a version suffix, and upload "
             "it with a note listing both versions."},
    {"heading": "Subject summary", "help": "One line for the email subject, written once you know what went wrong."},
]
MAILTO_LIMIT = 1800  # some mail apps cut longer mailto links short, so stay well under ~2,000 characters


class NoteConflict(Exception):
    """The section was changed elsewhere since the screen showed it."""


def note_view(folder):
    note = paths.load_engine("note")
    sections = note.read_sections(_read(folder))
    empty = note.empty_sections(sections)
    answers = {h: ("" if h in empty else sections[h]) for h in note.MINE}  # placeholders shown as empty boxes
    summary = answers["Subject summary"] or "…"
    return {"ok": True, "report_id": folder.name,
            "from_check": {h: sections[h] for h in note.FROM_CHECK},
            "answers": answers, "empty": empty, "questions": QUESTIONS,
            "subject_preview": f"Delivery issue: {summary} (PROBLEMS FOUND)",
            "private": {"causes": sections.get(note.PRIVATE[0], ""), "triage": sections.get(note.PRIVATE[1], "")},
            "has_email": bool(_emails(folder))}


def save_answer(folder, heading, text, expected):
    note = paths.load_engine("note")
    files = paths.load_engine("files")
    current_text = _read(folder)
    sections = note.read_sections(current_text)
    current = "" if heading in note.empty_sections(sections) else sections.get(heading, "")
    if current.strip() != (expected or "").strip():
        raise NoteConflict(f"“{heading}” was changed somewhere else since this screen showed it. "
                           "The latest text is shown now; your typing wasn't saved.")
    if heading == "Subject summary":
        text = " ".join(text.split())  # a subject line is one line
    files.replace_safely(_note_path(folder), note.set_section(current_text, heading, text))
    return note_view(folder)


def make_email(folder):
    note = paths.load_engine("note")
    manager_email = paths.load_engine("manager_email")
    sections = note.read_sections(_read(folder))
    missing = note.empty_sections(sections)
    if missing:
        return {"ok": False, "missing": missing,
                "error": "Still empty: " + ", ".join(missing) + ". The email is made only when all five are answered."}
    text = manager_email.build_email(sections)
    path = manager_email.save_email(folder, text)  # never overwrites: a second one is manager-email-2.txt
    subject, _, _ = text.partition("\n")
    return {"ok": True, "subject": subject.removeprefix("Subject: "), "file": Path(path).name, "text": text,
            "parts": [{"heading": h, "text": sections[h]} for h in manager_email.ORDER]}


def latest_email(folder):
    emails = _emails(folder)
    return max(emails, key=_email_number).read_text(encoding="utf-8") if emails else None


def mailto_url(subject, body):
    """A new email draft in the default mail app. Fills the body only when the link stays short
    enough for every mail app; returns (url, body_included)."""
    base = "mailto:?subject=" + quote(subject, safe="")
    with_body = base + "&body=" + quote(body.replace("\r\n", "\n").replace("\n", "\r\n"), safe="")
    return (with_body, True) if len(with_body) <= MAILTO_LIMIT else (base, False)


def split_email(text):
    """manager-email.txt is "Subject: …", a blank line, then the body."""
    first, _, rest = text.partition("\n")
    return first.removeprefix("Subject: ").strip(), rest.lstrip("\n")


def _note_path(folder):
    return Path(folder) / "incident-note.md"


def _read(folder):
    return _note_path(folder).read_text(encoding="utf-8-sig")


def _emails(folder):
    return [p for p in Path(folder).glob("manager-email*.txt") if re.fullmatch(r"manager-email(-\d+)?\.txt", p.name)]


def _email_number(path):
    match = re.fullmatch(r"manager-email-(\d+)\.txt", path.name)
    return int(match.group(1)) if match else 1
