# Delivery Desk (app): design

Status: **Approved by Georgi on 2026-10-11.**

## 1. The problem

[delivery-desk](https://github.com/Georgie995/delivery-desk) runs my delivery tools as one flow, but only from the command line. The people who most need clear delivery checks often aren't comfortable there: coordinators, producers, other operators.

This app is for **"anyone who might need to use it but isn't comfortable with the command line."** It is the same tested engine with a calm, plain-language window on top. The command line keeps working alongside it.

**The pitch:** a drag-and-drop desktop app that checks media deliveries for missing or corrupted files, and turns any problems into a clear incident email. It makes technical checking calm and approachable for non-technical users.

## 2. Decisions already made (from the kickoff, in `research/`)

| Topic | Decision |
|---|---|
| Look | **"Paper"**: calm and light, with an off-white background, a soft grey sidebar, serif headings (Newsreader), Instrument Sans for text, and IBM Plex Mono for file names. **No dark mode.** The prototype canvas is the visual reference. |
| Screens | All eight: Start, Checking, All clear, Problems found, Incident note, Email ready, Settings, Earlier checks (plus the Recent list in the sidebar). |
| Platform | **Windows first.** Mac stays possible later, but is untested, and the README says so. |
| Starting it | A **desktop shortcut** while building. A **packaged Windows app** (double-click, nothing else to install) is the last module. |
| Alerts | **Optional.** The app always works with just the checker. If delivery-ops-hub is set up, it also sends the alert and logs the check. |
| Reports folder | Alerts off: the **Reports folder** from Settings. Alerts on: delivery-ops-hub's own reports folder, so alerts, log and app always agree. |
| Secrets | The webhook secret and the AI key are typed into password boxes in Settings and stored in **Windows Credential Manager**. They're never written to any file, log, note or email. |
| Progress | **Real progress** while checking: files done out of the total, the current file, and time left. |
| Problem titles | **Friendly titles** on screen, with the manifest-doctor code in small print. **Georgi reviews every title.** The email keeps the codes, unchanged. |
| Report button | **"Show report in folder"** opens the report folder in File Explorer. No copies are made. |
| Name and repo | The app is called **Delivery Desk**, in its own repo, `delivery-desk-app`. delivery-desk stays "standard library only". |
| Before any push | **Georgi tries the finished app himself** before anything goes to GitHub, including the engine changes. |

## 3. How it's built: three layers

```
┌──────────────────────────────────────────────────────────────┐
│ 1. PAGES      HTML + CSS + a little JavaScript, one file per │
│               screen, adapted from the prototype. Fonts are  │
│               bundled locally.                               │
├──────────────────────────────────────────────────────────────┤
│ 2. BRIDGE     One small Python class the pages can call      │
│               (pywebview's js_api): choose a folder, start a │
│               check, read progress, save an answer, make the │
│               email, list earlier checks, settings, secrets. │
├──────────────────────────────────────────────────────────────┤
│ 3. ENGINE     What already exists and is tested: delivery-   │
│               desk (note, email, check), manifest-doctor,    │
│               and, optionally, delivery-ops-hub and          │
│               ai-triage, run as separate programs as now.    │
└──────────────────────────────────────────────────────────────┘
```

**Words used here:**
- **pywebview:** shows web-style pages inside a real Windows window, using the Edge engine built into Windows. It was chosen after research, and a hands-on test on Georgi's PC confirmed that dropped folders and files give their real locations (`research/app-toolkit-research.md`).
- **The bridge:** the only way the pages can ask Python to do anything.

**Why three layers:**
- Pages only *show* things.
- The bridge holds the app's logic, and is plain Python, so **it can be tested with pytest without opening a window.**
- The engine is unchanged except for the two small additions in section 4.
- No new decision about deliveries is made in the app.

**Lesson from the hands-on test:** pages live in their own `.html`/`.js` files, served with pywebview's built-in local server. JavaScript is never written inside Python strings.

## 4. Engine changes needed (each test-first, in its own repo)

1. **manifest-doctor: an opt-in progress file.**
   - A new option, `--progress-file PATH`. While checking, it keeps a tiny JSON file up to date: files done, total files, bytes done, total bytes, current file.
   - It's written safely (a temporary file, then a swap) at most a few times a second.
   - It's off unless asked for, so the default behaviour and the existing 149 tests are unchanged.
   - **Why a file and not printed output:** when alerts are on, delivery-ops-hub runs manifest-doctor and holds on to its printed output until the end. delivery-ops-hub already passes extra options to manifest-doctor unchanged, so a progress *file* works on both routes **with no change to delivery-ops-hub**.
2. **delivery-desk: a "check without alerts" route.**
   - When alerts aren't set up, run manifest-doctor directly (reports into the Reports folder), then ai-triage if set up, then write the working note for PROBLEMS FOUND, exactly as now.
   - **Also:** a way to hand the secrets to the child programs (as environment variables, for that one run only) instead of reading them from the computer's environment.
   - The command line keeps its current behaviour and tests.

## 5. The screens and what drives them

| Screen | What the app does underneath |
|---|---|
| **Start** | Drop or choose a folder and a manifest. pywebview gives their real locations. The cards show the name, location and file count (the "Added" state from the prototype). |
| **Checking** | Runs the check in the background, so the window never freezes. Reads the progress file a few times a second to drive the bar, the counts, the current file and the time left. **Stop checking** ends the check program; nothing is changed, because checking is read-only. |
| **All clear / Problems found** | Reads `report.json`. Friendly titles come from a wording table in the app, and unknown codes are shown as the code itself. Probable causes are labelled "hints, not verdicts". **Show report in folder** opens File Explorer. |
| **Incident note** | One question at a time. Each answer is saved straight into `incident-note.md` using delivery-desk's own tested code (only empty sections are filled, and it never overwrites). The private part is shown, but never put in the email. |
| **Email ready** | delivery-desk writes `manager-email.txt` (never overwritten, `-2` next time). **Copy email** puts it on the clipboard. **Open in mail app** opens a new draft in the default mail app. The app never sends anything. |
| **Earlier checks / Recent** | Reads the reports folder: each `report-*` folder, with its result, note progress (e.g. "3 of 5 answered") and whether an email exists. There's no database, so it can't drift from the files. |
| **Settings** | Locations and secrets, as in the prototype (version 16). Settings live in a small file in the user's app-data folder; **secrets never go there**. |

## 6. Safety rules

Everything from the earlier projects still applies: read-only checks, nothing ever sent, nothing overwritten, synthetic data only. Specific to the app:

- **File names are shown as text, never as page code.** A delivery could contain a file named like a piece of web page code, for example `<img onerror=…>`. If the page treated it as code, it could run inside the app and call the bridge.
  - **All report data goes into the page as plain text only,** never as HTML.
  - **The pages also carry a Content Security Policy:** a rule telling the window to run only the app's own scripts.
  - **A test uses exactly such a file name.**
- **The bridge only does what the screens need.** It has no "run any command" and no "delete" functions, and it checks every path it's given.
- **The app makes no network calls of its own.** Fonts and pages are local. The only network traffic is what the optional tools already do: delivery-ops-hub's alert to n8n, and ai-triage's AI call when a key is set.
- **Secrets:** read from Credential Manager only at the moment a tool runs, then handed to that one program run. Never logged or shown again.

## 7. Testing plan

- **Engine changes:** test-first, in manifest-doctor and delivery-desk, with their existing suites still passing.
- **The bridge:** pytest, without opening a window. That includes progress reading, the earlier-checks listing, settings, secret handling (with a stand-in for Credential Manager, so tests never touch your real saved passwords), and the injection-style file name.
- **Pages:** a few automatic window checks, like the self-check from the hands-on test. Each opens the window, drives a screen and reads back what's shown.
- **Your hands-on review** before anything is pushed.

## 8. Build order (modules)

1. **Engine:** the manifest-doctor progress file, plus delivery-desk's no-alerts route and secrets hand-off. Committed locally, **not pushed**.
2. **App skeleton:** the window, Start and Settings, drop and choose, settings and secrets.
3. **Checking and results:** progress, All clear, Problems found, friendly titles (your review), Show report in folder.
4. **Incident note and Email ready:** answers saved as you go, Copy, Open in mail app.
5. **Earlier checks and Recent.**
6. **Your hands-on review:** you browse the app, and I fix what you find.
7. **Packaging:** the double-click Windows app.
   - **Known risk:** inside a packaged app, there's no separate Python to start the tools with. I'll research the standard solution (the app starting a copy of itself in "tool mode") at that module, before choosing.
   - Then the README, the safety search, publishing (after your OK), your profile page, and the end-of-project quiz.

## 9. Not in this version

Mac build, dark mode, filling manifest gaps (A), the rename preview (B), a client-email draft, and any new AI.

## 10. Answered questions

1. **"Open in mail app" and long emails: answered, (a).**
   - **Copy email** is the main button.
   - **Open in mail app** fills in the subject and as much of the body as fits safely.
   - When the email is too long, it fills only the subject and says "Paste the email from the clipboard."
