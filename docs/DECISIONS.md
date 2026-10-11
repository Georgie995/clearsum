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
- **Friendly titles** for all 20 codes are drafts awaiting Georgi's review. An unknown code is shown as itself.
- **Limits:** up to 500 findings on screen, with the total shown, and 10 files per probable cause, as in the working note. The full lists are always in the report files.
