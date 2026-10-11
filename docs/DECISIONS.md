# Decisions

Each entry records the decision, the alternatives considered and why this one was chosen. The kickoff decisions (look, screens, platform, alerts, secrets, progress, titles, name) are summarised in `DESIGN.md` section 2.

## 2026-10-11: pywebview for the window

- **Decision:** the app's screens are HTML/CSS pages shown in a native Windows window by pywebview, which uses the Edge engine built into Windows.
- **Why:**
  - Georgi's prototype is HTML/CSS, so it can be reused almost as-is.
  - A hands-on test on his PC confirmed that dropped folders and files give their real locations, and that the Choose pickers work.
- **Rejected:**
  - Qt (PySide6): every screen would have to be rebuilt, the core download alone is about 82 MB, and the result would be the least faithful to the prototype.
  - A plain browser page: browsers hide dropped files' locations, and it doesn't feel like an app.
- Details: `research/app-toolkit-research.md` (private notes).

## 2026-10-11: Three layers: pages, bridge, engine

- **Decision:**
  - **Pages** only show things.
  - **The bridge** (`bridge.py`) is the only thing pages can ask Python to do, and is tested with pytest without a window.
  - **The engine** is delivery-desk, manifest-doctor and the optional tools, unchanged apart from two small additions made in their own repos.
- **Why:** each layer can be checked on its own, and no new decisions about deliveries are made in the app.

## 2026-10-11: A strict security policy on every page

- **Decision:** the page allows only the app's own scripts, styles and fonts (`Content-Security-Policy`, with no inline scripts or styles and no remote content).
  - **Tested first:** pywebview's bridge works fully under this policy, and the policy blocked a deliberately injected "file name" even when it was inserted the unsafe way.
- **Also:** everything that comes from a delivery or the computer goes into the page with `textContent` (as text), never as HTML.
- **Why:** a delivery could contain a file named like web page code. If the page ran it, it could call the bridge. Two independent layers mean one mistake isn't enough.

## 2026-10-11: The bridge exposes exactly nine actions

- **Decision:** `choose_folder`, `choose_manifest`, `choose_path`, `describe_folder`, `describe_manifest`, `get_settings`, `save_settings`, `save_secret`, `remove_secret`.
  - Everything else starts with `_`, and pywebview doesn't expose those.
  - **A test fails if any action is added** without updating it, so a new power has to be a conscious choice.
- **None of them deletes, moves or changes anything in a delivery.**

## 2026-10-11: Settings are locations only, in the user's app-data folder

- **Decision:** `%APPDATA%\Delivery Desk\settings.json`, saved in one step.
  - **Unknown fields are refused,** so a secret can never be saved there, even by mistake.
  - **A damaged settings file is reported, not silently replaced.**
- **Pairs:** delivery-ops-hub's folder and its settings file, and ai-triage's folder and its Python, must be set together or not at all. A mistake comes back naming the box that needs fixing.
- **Reports folder rule (Georgi's):** while alerts are set up, delivery-ops-hub's own reports folder is used, so alerts, log and app agree. Otherwise, the Reports folder from Settings.

## 2026-10-11: Secrets in Windows Credential Manager, via `keyring`

- **Decision:** typed into password boxes and saved under the name "Delivery Desk".
  - **The page only ever learns whether a secret is saved,** never its value. The password box is emptied straight after saving.
  - **Tests use a stand-in, so they never touch the real Credential Manager.**
- **Status wording:**
  - **Alerts:** "Needs the webhook secret" when the locations are set but the secret isn't.
  - **AI:** "Set up, no AI key" when ai-triage is set up but the key isn't. The summary is then written by code, which still works.

## 2026-10-11: Drops are handled in Python

- **Why:** only Python learns a dropped item's real location (pywebview adds it to the drop event).
- **Decision:**
  - The handler describes the item, then calls the page with the result.
  - Everything is passed through `json.dumps`, so a name containing quotes, `</script>` or unusual line separators can't break out of the call.
  - **Several items at once:** "Add one item at a time."
  - **No real location (for example dragged from a browser):** "Try the Choose button instead."

## 2026-10-11: File names in this package avoid Python's built-in names

- **Decision:** `secret_store.py`, not `secrets.py`. Python has a built-in `secrets` module, the same reasoning as delivery-desk's `manager_email.py`.

## 2026-10-11: Module 2 tests

- **37 tests:**
  - the bridge, settings and secrets, without a window;
  - drops, without a window;
  - **an automatic window test:** it opens the real app for a few seconds, drives it, records what it shows, and closes it.
- **The window test was written after the pages, not before,** so its protections were proven by breaking them instead. 9 protections were broken on purpose, and every one was caught.

## 2026-10-11: Checks run in the background; the screen asks how they're going

- **Decision:**
  - `start_check` hands the work to delivery-desk's engine on a background thread, so the window never freezes.
  - The page asks `check_status` a few times a second.
  - Progress comes from manifest-doctor's progress file, which sits in the system's temporary folder, never inside the delivery, and is tidied away afterwards.
  - **Only one check runs at a time.**
- **Time left:** worked out from how fast data has been read so far. It's shown only once reading has properly begun, so it's never a guess.
- **Stop:** passed straight to the engine, which ends the checking tool and anything it started.
- **A problem starting a check** (for example a settings mistake) is shown in plain words, and is never a crash.
- **Found while testing:** on Windows, a file can't be deleted at the instant another part of the app is reading it. Tidying up the progress file now tries again briefly, rather than letting an error escape. A test forces that moment every time.

## 2026-10-11: The engine's settings depend on whether alerts are set up

- **Alerts set up:** the check goes through delivery-ops-hub, with the webhook secret from Credential Manager. Reports land in delivery-ops-hub's reports folder, under Georgi's rule.
- **Otherwise:** manifest-doctor runs directly into the app's Reports folder.
- **Either way:** ai-triage is used if it's set up, with the AI key if one is saved.

## 2026-10-11: Results and "Show report in folder" only ever reach real report folders

- **Decision:** the page asks for a result by report name only, such as `report-2026-10-11_160742`. The name must look exactly like a manifest-doctor report folder, sit directly inside the reports folder in use, and contain a `report.json`.
- **Why:** a name from the page can never reach anywhere else on the computer. "Show report in folder" opens only a checked report folder in File Explorer, never an arbitrary path, which on Windows could otherwise open a program.

## 2026-10-11: Results in plain words

- **Headlines:**
  - **Clean:** "All 1,204 files match the manifest."
  - **Warnings only:** "Every file arrived intact", plus how many warnings.
  - **Problems:** "N files didn't arrive as expected." This counts *files*, not findings: one file listed twice and mismatched is still one file.
  - **Only manifest problems:** "The manifest itself has problems."
- **Friendly titles** for all 20 codes: written from manifest-doctor's code, **reviewed and approved by Georgi**. An unknown code is shown as itself.
- **Limits:** up to 500 findings on screen, with the total shown, and 10 files per probable cause, as in the working note. The full lists are always in the report files.

## 2026-10-11: The Checking screen's three steps follow what manifest-doctor really does

- **Decision:**
  1. "Reading the manifest and the folder" (its "preparing" stage).
  2. "Reading files and working out checksums" ("hashing").
  3. "Comparing and looking for likely causes" (after the last file is read).
- **Why:** the prototype's three steps were in a different order from the real work. The screen should never describe something that isn't happening.
- **The percentage follows data read,** not files counted, because one large file can take as long as thousands of small ones.

## 2026-10-11: Passed-with-warnings uses the Problems layout; All clear is only for CLEAN

- **Why:** warnings have findings worth showing (the table, likely causes), but no working note, because notes are for PROBLEMS FOUND only (Georgi's rule). The pill says "PASSED WITH WARNINGS" in amber, and "Start incident note" is hidden.

## 2026-10-11: A "The check couldn't run" screen (not in the prototype)

- **When:** the checking tool stopped before verifying anything, for example with an empty manifest, or when delivery-ops-hub couldn't run.
- **Shows:**
  - a plain reason;
  - "Nothing was verified, and nothing in the delivery was changed";
  - the tools' own last messages, word for word;
  - "Back to the check" (the selections are kept) and "Open Settings".
- **Same Paper style as the rest of the app.** For Georgi to review in the app.

## 2026-10-11: The alert line is worded from what delivery-ops-hub actually said

- **Decision:** shown only when alerts are set up. "NOT DELIVERED" in delivery-ops-hub's messages becomes "Not delivered to n8n. It is waiting in delivery-ops-hub's outbox…", and "ALERT FAILED" becomes "Logged, but the alert itself failed. Tell the team directly." Otherwise it says the check was logged, and that alerts go out for deliveries with problems.
- **Why:** the app shouldn't claim an alert was sent when it wasn't. The tools' full messages are always available under "Show what the tools said".

## 2026-10-11: Real checks in the real window, as a test

- **Decision:** `test_window_check.py` opens the app and runs real checks through delivery-desk and manifest-doctor on three synthetic deliveries:
  - one with a file listed twice, **plus a manifest line naming a file `<img … onerror=…>`**;
  - one clean;
  - one with an empty manifest.
- **Why the odd file name:** Windows doesn't allow such names on disk, but a manifest can list any name, and a delivery from a Linux machine could hold one. On screen it must be plain text that does nothing.
- **Two weaknesses found in the test itself while proving it, and fixed:**
  - its "no leftover progress files" check was looking in the wrong folder, so it could never fail;
  - it had no hostile name on the results screen.
- **6 protections were broken on purpose, and every one was caught.**
- **Not covered in the window:** pressing Stop mid-check. A real check of a tiny delivery is over too fast to stop. Stop is covered by the engine's tests (a program and its child are both ended) and the background-check tests.

## 2026-10-11: The incident note is written through delivery-desk's own code

- **Decision:** the note screen reads and writes `incident-note.md` with delivery-desk's `read_sections`, `set_section` and `replace_safely`, and the email is made with its `build_email` and `save_email`. The app adds no rules of its own about the note's format.
- **Why:** one tested definition of the note, shared by the command line and the app.

## 2026-10-11: Each answer is saved as you move on, and never over someone else's edit

- **Decision:**
  - **Saving:** each answer is written into the note when you press Next or Back, pick another question, or leave a "from the check" box.
  - **The guard:** the app saves only if that section still says what the screen last showed. If it was changed in a text editor meanwhile, the save is refused, the latest text is shown, and a message explains what happened.
- **Tested in the real window:** the note is changed in Notepad mid-way, then the person types and presses Next. Notepad's text is kept.

## 2026-10-11: The subject summary is one line

- **Decision:** its question uses a single-line box, and any line breaks become spaces when saved, because an email subject can't contain them. This is the same rule as delivery-desk's email.

## 2026-10-11: Copy uses Windows' own clipboard functions

- **Decision:** a small module, `clipboard.py`, calls Windows directly, so no extra library is needed. The email is copied with Windows line endings, so it pastes cleanly everywhere.
- **Testing:** the tests use a stand-in, so running them never replaces what you have copied. **The real clipboard is checked by hand in Georgi's review.**

## 2026-10-11: "Open in mail app": the subject and body when they fit; otherwise the subject plus the clipboard

- **Decision (Georgi's option a):** the draft opens with a `mailto:` link.
  - **Limit:** if the link would be longer than 1,800 characters (some mail apps cut longer links short), only the subject goes in the link. The whole email is put on the clipboard, and the screen says "paste it in".
- **Safety:**
  - every character in the link is encoded, so `&` or `%` in an answer can't break it;
  - only a `mailto:` link the app built itself is ever opened;
  - **the app never sends anything.**

## 2026-10-11: Found while testing: "finished" must come after tidying up

- **Problem:** a background check was marked "finished" a split second before its temporary progress file was removed. The screen could, in theory, see "finished" with the file still there.
- **Fix:** the end state is now set last of all. A test that had passed before caught this when run alongside the new tests.

## 2026-10-11: Module 4 tests

- **92 tests**, including the whole flow in the real window:
  - a real check;
  - Start incident note;
  - five answers typed through the screen;
  - rewording "The problem";
  - Make the email;
  - Copy, and Open in mail app (with stand-ins);
  - Edit my answers, and the Notepad cases.
- **An answer that looks like web page code** is plain text in the email preview.
- **6 protections were broken on purpose, and every one was caught.**

## 2026-10-11: Earlier checks are read from the reports folder, never from a database

- **Decision:** the list is rebuilt from the report folders each time: `report.json` for the result, plus the presence and progress of `incident-note.md` and `manager-email*.txt`. Report headers already read are remembered while the app is open, keyed by file size and time, so a long list stays quick.
- **Why:** nothing can drift. Delete or move a report folder, and it simply isn't listed.
- **Note progress words:**
  - "Not started";
  - "3 of 5 answered";
  - "Email ready";
  - "No note needed" (clean or warnings);
  - "Note needs attention" (its headings were changed by hand, so it's flagged, not hidden).
- **Limits:** the newest 200 are listed, and the total is counted. Half-written or damaged reports are skipped quietly; the folders themselves are never touched.
- **Which folder:** the one in use, by Georgi's rule. With alerts set up, that's delivery-ops-hub's reports folder.

## 2026-10-11: Reopening a check continues where you left off

- **Decision:** clicking a row, or a Recent item, opens that result. The note button then reads:
  - "Start incident note" (not started yet);
  - "Continue incident note" (some answers saved);
  - "Open incident note" (email ready, or the note needs attention).
- **No live alert line or tool messages for an earlier check:** they belong to the moment it ran, and the report folder holds the full record.
- **The Recent list** in the sidebar shows the latest five. Problems show their note progress, for example "Email ready · today".

## 2026-10-11: Module 5 tests

- **105 tests.** The window tests list real checks, search, reopen one, and see "Email ready" appear after making an email.
- **A synthetic old report with a delivery name that looks like code** (as a report made on a Linux machine could carry) is plain text in both lists.
- **6 protections were broken on purpose, and every one was caught.**

## 2026-10-11: Georgi's hands-on review (module 6)

- **What he did:** used the app himself on synthetic practice deliveries, following `practice/app-review/REVIEW-CHECKLIST.md`.
- **Verdict, in his words:** "everything works well, fast, clear and looks neat, tidy, minimalistic." No changes were requested.
