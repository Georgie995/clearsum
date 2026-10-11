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

---

## Module 3: checking and results

**In one sentence:** press "Check delivery", watch it work through the delivery with a real progress bar, and get a plain-language answer: all clear, problems found (with what probably happened), or "the check couldn't run" with the reason.

**Like this:** handing a delivery to a careful colleague.
- **While they work,** they tell you how far through they are, which file they're reading, and roughly how long is left.
- **If you change your mind,** you can say "stop", and they stop straight away, having touched nothing.
- **When they're done, you get one of three answers:**
  - **All clear:** "All 1,204 files match the manifest", and a list of everything they looked for, each marked "None".
  - **Problems found:**
    - how many *files* didn't arrive as expected, not how many individual complaints there were;
    - their best guess at what happened, labelled as a hint and not a verdict;
    - the full list of findings, which you can filter to errors, warnings or info.
  - **Couldn't check:** why, in plain words, plus the tools' own words, and the reassurance that nothing was verified or changed.
- **"Show report in folder"** opens the report's folder in File Explorer, but only ever a real report folder.

**Under the hood, in plain words:**
- **The check runs "in the background",** so the window never freezes, however big the delivery.
- **The progress bar reads the little progress note** that manifest-doctor writes while it works (module 1). Time left is worked out from how fast it has been reading so far.
- **Friendly titles** such as "Checksum doesn't match the manifest" sit beside the codes. You reviewed and approved all 20.

**Things it is careful about:**
- **A file name can't take over the app,** on the results screen either. A test checks a manifest that lists a file called `<img … onerror=…>`: it shows up as plain text and does nothing.
- **The temporary progress note is always tidied away.** A test found that Windows sometimes refuses to delete it at the exact moment the screen is reading it, so the app now waits a moment and tries again.

**Tested by:** 72 automatic tests. That includes **real checks in the real window** on three made-up deliveries (problems, clean, and can't be checked). Six protections were broken on purpose, and a test caught each one.

---

## Module 4: the incident note and the email

**In one sentence:** from a problem result, press "Start incident note", answer five questions one at a time, and get the email for your manager, ready to copy or open in your mail app.

**Like this:** the paper incident form from delivery-desk, but on screen.
- **The top** shows what the check already knows: which delivery, and the problem. You can reword either.
- **Then one question at a time,** with a hint under each, and Back and Next. A list on the side shows which of your five are answered.
- **A private panel** shows the likely cause and ai-triage's summary, to help you investigate. It never goes in the email.
- **Every answer is saved into the note as you move on,** so closing the app halfway loses nothing.
- **When all five are answered,** "Make the email" shows it exactly as it will be sent: the subject line and your six parts, your words unchanged. Then you can:
  - **Copy email,** and paste it into any email;
  - **Open in mail app,** which starts a new draft. If the email is too long for that, your mail app opens with just the subject, and the email is waiting on the clipboard to paste in;
  - **Show in folder,** which shows where `manager-email.txt` was saved. Making it again never overwrites it.

**Things it is careful about:**
- **It never sends anything.** You do.
- **If you change the note in Notepad while the app is open,** the app won't type over it. It shows you the latest text and explains why.
- **An answer that looks like web page code is just text** in the email.

**Tested by:** 92 automatic tests, including the whole journey through the real window: a real check, the five answers, the email, Copy, and Open in mail app. Six protections were broken on purpose, and a test caught each one.
