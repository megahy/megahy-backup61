# 0.4.0-rc6 (2026-11-23)

- Fix an extra comma in the Arabic interface text table that prevented all JavaScript from loading in rc4. Browse, Start and Continue handlers now load again.
- Add reproducible headless Chromium click tests and JavaScript syntax checks. Prior rc4 engine tests did not test interface script parsing.
- No backup format or engine behavior changes. Existing interrupted folders are kept.
- Still simulation-only, not tested on real Windows or a phone.

# Changes

## 0.4.0-rc4, 2026-11-23, release candidate
Requested by the owner after his first long run stopped when Windows slept and
the phone disconnected: he wants to stop whenever and continue the same backup
where it left off, not start over.
1. Continue an interrupted backup. Stop, disconnect, error, crash or PC sleep
   no longer force a new dated folder. The app finds the newest interrupted
   folder in the destination and offers to continue it (also from the status
   card after a stopped/failed run). Files already hash-verified in an earlier
   session are trusted as-is; pending and failed files are copied and verified
   fresh. A verified PC copy that was deleted or truncated is copied again.
   Each run writes run-state.json at start, so even a crash-killed run keeps
   its selection provable. rc3-made folders can be continued when their final
   report exists. The original selection is kept on continue.
2. Mid-file resume: files of 4 MiB or more copy in 8 MiB ranged reads
   (adb exec-out dd). Completed chunk SHA-256s are recorded in a sidecar;
   a later session re-hashes the partial and keeps it only up to the last
   matching chunk. The whole-file triple hash check still gates every verified
   file, and a mismatch discards the partial. Phones/ADB without ranged reads
   fall back to whole-file copies with a warning.
3. Windows sleep prevention: while a run is active the app calls
   SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED). The request
   ends with the run or the process; the screen may still turn off, and lid
   closing, low battery or manual Sleep still interrupt the run.

Testing: see TESTING.md. rc4 checks are again Linux simulations with a
synthetic ADB process; no real phone or Windows PC ran this candidate. The
keep-awake call is verified by code inspection only.

## 0.4.0-rc3, 2026-11-23, release candidate
Requested by the owner after trying rc2 on his PC and phone:
1. In-app notice: removed the sentence about the earlier user-reported run and
   simulation-only testing, in English and Arabic. The full testing status
   stays in README, TESTING.md and TEST-RESULTS.
2. Browse... folder picker now opens in front of the browser window. In rc2 it
   could open behind the browser, looking as if nothing happened
   (owner-reported). The picker is shown owned by an invisible top-most
   window. Verified by code inspection on Linux; still to be confirmed on a
   real Windows PC.

Testing: see TESTING.md. rc3 checks are again Linux simulations with a
synthetic ADB process; no real phone or Windows PC ran this candidate.

## 0.4.0-rc2, 2026-11-23, release candidate
Requested by the owner after rc1:
1. Browse button: the "Backup parent folder" field gains a Browse... button
   that opens the native Windows folder picker (PowerShell
   FolderBrowserDialog). If the picker cannot open (non-Windows host, or
   PowerShell unavailable), the app reports it and the field stays manual.
   The button is disabled while a run is active, like the text field.


## 0.4.0-rc1, 2026-11-22, release candidate
New features (requested by the owner, in order):
1. Incremental backup: files whose size and modification time match an earlier
   verified backup in the same destination are skipped; same-size files without
   trustworthy timestamps must match the earlier SHA-256 before being skipped.
   Skipped files stay in the earlier dated folder, which the manifest names.
   On by default; a checkbox turns it off for a full comparison.
2. ADB auto-setup: one click downloads Google's official Platform-Tools ZIP
   from dl.google.com, checks its size, integrity and layout, and extracts it
   next to the app. Manual placement still works.
3. Hash verification after copy (already in 0.3.x): unchanged.
4. Saved settings and named profiles: destination, selection, theme and
   language persist in settings.json on the PC; profiles store named
   destination+selection pairs.
5. Original file dates: copies keep the phone's modification time
   (adb pull -a plus an explicit timestamp restore from stat metadata).
6. Wi-Fi backup (Android 11+ wireless debugging): pair and connect from the
   UI, then run any backup or restore over Wi-Fi.
7. Scheduled backups: one click registers a Windows scheduled task that runs
   an unattended backup (--auto) with the saved settings; the last automatic
   run is shown in the UI and last-auto-run.json.
8. Restore to phone: copies verified files from a chosen backup folder back
   into a dated folder on the phone and re-verifies each SHA-256 after push.
   Restore writes to the phone; backup runs remain read-only.
9. Dark mode and a full Arabic (RTL) interface, switchable in the header.

Brand neutrality:
- Removed all MIUI/Redmi/vendor-specific wording and the MIUI backup counter;
  vendor backup folders are now ordinary copy candidates like any other files.
- Removed the CableVault name from the app UI, docs and source headers. A short
  provenance note remains in NOTICE.txt (the preview was the author's own work).

Extras added:
- Free-space precheck: the run refuses to start when measured selected bytes
  exceed free space at the destination.
- The report records skipped-unchanged counts and source modification times.
- Faster repeat ETA on incremental runs (skipped files count as completed work).

Testing: see TESTING.md. All checks are Linux simulations with a synthetic ADB
process; no real phone or Windows PC ran this candidate. Wi-Fi pairing,
scheduling and restore in particular are simulation-tested only.

## 0.3.1-rc2, 2026-11-22, private release candidate
- Owner chose GPLv3: application license changed from the proposed MIT to GPLv3-or-later (LICENSE.txt now carries the full GPLv3 text).
- Retained the inherited CableVault MIT notice verbatim in the new NOTICE.txt, as MIT requires; source headers now read SPDX GPL-3.0-or-later.
- Updated README, UI footer, contribution and release-checklist wording, and added the GPLv3 corresponding-source distribution note.
- No code, test or packaging behavior change beyond version labels.

## 0.3.1-rc1, 2026-11-22, private release candidate
- Added Marwan Megahy's copyright credit while retaining the existing MIT/CableVault notice. Corrected stale filenames in license scope.
- Added clear Windows PC architecture/OS/setup limits and explained why no-special-installs does not remove ADB/driver/phone authorization requirements.
- Added source-release preparation, license comparison, third-party/runtime provenance, privacy, contribution, security and release-checklist documents.
- Removed the irrelevant missing-MIUI-backup warning on other brands. Existing readable MIUI files are still ordinary copy candidates. Hide the MIUI counter when zero.
- Added visible legal credit in the UI and aligned candidate version labels.
- Added release-audit/build utilities and draft cross-platform unit-test CI configuration. No publication or CI execution occurred.
- Kept backup engine behavior, verification, selection and Pause/Resume/Stop otherwise unchanged.

## 0.3.0
Original selective-copy preview supplied by the owner. Original code and test fixtures retained, except the documented changes above. See TEST-RESULTS-v0.3.0.txt for historical checks.
