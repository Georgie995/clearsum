# Walkthrough

A plain-English explanation of each part, written for someone with no technical background.

---

## Module 1: two small upgrades to the engine

**In one sentence:** before building the app, two tools underneath it learned a new trick each.

1. **manifest-doctor can report how far it's got.** When asked, it keeps a tiny note up to date while it checks: "312 of 1,204 files, now reading clip_0312.mov". That's what will move the app's progress bar. It's switched off unless asked for, so manifest-doctor behaves exactly as before for everyone else. If the note can't be written, the check carries on regardless, because the report is what matters.
2. **delivery-desk can work without alerts, and hands out secrets carefully.** If nobody has set up delivery-ops-hub, it now runs the checker directly. When the app passes it the passwords, each tool gets **only its own**, for that one job: the alert password only to the alert tool, the AI key only to ai-triage, and the checker gets neither.

---

## Module 2: the app's skeleton

**In one sentence:** the Delivery Desk window opens, you can add a delivery folder and its manifest by dragging them in or choosing them, and Settings remembers where things are and keeps passwords in Windows' own password safe.

**Like this:** think of a shop.
- **The shop front** is the window: your Paper design, with the sidebar, the two big cards and the Settings screen.
- **The counter** is the "bridge": the only way the shop front can ask for anything to be done. It has exactly nine things it will do, and a test complains if anyone adds a tenth without meaning to.
- **The back room** is the tools you already built.

**What works now:**
- **Drag a folder or a manifest onto its card,** or use Choose. The card turns green and shows the name, the location and how many files or entries it has. Drop the wrong thing (a file on the folder card, say) and you get a plain explanation.
- **"Check delivery" wakes up** once both are added. For now it says checking arrives in the next part of the build.
- **Settings:**
  - **Standard** shows what's set up.
  - **Advanced** has the locations, with Browse buttons, and the password boxes.
  - A mistake comes back pointing at the exact box to fix.
  - **Saving a password** puts it in Windows Credential Manager, empties the box, and from then on the app only says "Saved". It never shows the password again.

**Things it is careful about:**
- **A file name can't take over the app.** A delivery could contain a file named like a piece of web page code. The app always shows names as plain text, and on top of that, the window refuses to run anything that isn't the app's own code. A test tries exactly this trick.
- **Passwords never land in a file.** The settings file only accepts the known location fields, so a password can't end up there even by accident.

**Tested by:** 37 automatic tests. One of them opens the real window for a few seconds and drives it like a person would. Nine protections were also broken on purpose, one at a time, and a test caught every one.
