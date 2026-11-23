# rc5 interface regression checks, 2026-11-23

20 headless Chromium browser checks passed on Linux. Reproduced the exact rc4 parse error first, then checked Browse selection/cancel/error with a simulated picker, English and Arabic, theme, Start, Stop, both Continue controls, same-folder completion, session count and reload token persistence. Browser clicks drove the real local HTTP server and engine with synthetic ADB, not a mocked API.

40 engine checks also passed again. No real Windows, phone, USB, ADB or native folder dialog was used. The previous 40 engine checks missed rc4's UI syntax error. Every inline script in the delivered UI is now syntax-checked with Node before packaging.

## Inherited rc4 engine test coverage

# Candidate testing, 2026-11-23

Version: **0.4.0-rc6**. All checks are software simulations on Linux with a
synthetic ADB process and a mirror phone filesystem. **No real phone, real ADB,
real USB cable, real Wi-Fi link, Windows PC or Windows Task Scheduler ran this
candidate.** Treat Wi-Fi pairing, scheduling, restore, the keep-awake request
and ranged chunked copying as untested on hardware.

## The rc4 changes

1. Continue an interrupted backup (same folder after Stop, disconnect, error,
   crash or PC sleep), with verified files trusted as-is and everything else
   copied and verified fresh.
2. Mid-file resume: large files copy in 8 MiB ranged reads (adb exec-out dd)
   with a sidecar of chunk SHA-256s; the whole-file triple hash check still
   gates every verified file.
3. Windows sleep prevention during a run via SetThreadExecutionState.
   **Verified by code inspection only; needs a real Windows PC.**

## What passed (40 checks, 2026-11-23)

End-to-end through the real backup engine with a synthetic ADB and a 5-file
simulated phone (3 small photos, an Arabic-named note, one 20 MiB file):
- Full backup: all files hash-verified, zero failures; PC copies byte-identical
  to the phone; big file copied in 3 ranged chunk reads; no sidecar left behind.
- run-state.json written at start with selection and session number.
- A finished folder is correctly NOT offered as resumable.
- Stop after 2 files: run ends "Stopped, incomplete" and offers its folder as
  resumable; find_resumable reports 2 of 5 verified.
- Continue: same folder reused, original selection kept (a different posted
  selection is ignored), all 5 verified, folder byte-identical, report.json
  marks resumed session 2, manifest records a session marker, REPORT.txt
  explains the continued backup and keeps the not-safe-to-reset notice.
- Simulated disconnect inside the 20 MiB file after 2 chunks: run ends
  "Error, incomplete", the .partial and its .progress.json sidecar hold exactly
  2 chunks; continuing reads only the missing chunk (dd skip=2) and finishes
  byte-identical and verified.
- Corrupted partial bytes: the sidecar re-hash rejects the poisoned chunk, the
  file is re-copied from byte 0 and finishes verified.
- Ranged reads unavailable (no exec-out): one warning, whole-file adb pull
  fallback, all files verified byte-identical.
- rc3-style folder (no run-state.json, report.json says "Stopped, incomplete"):
  resumable from the report's selection, continues to full verification.
- Crash-killed folder without report or run-state: refused as unprovable;
  the API-level resume request is rejected.
- A verified PC copy deleted between sessions is re-copied, not trusted.
- Keep-awake on Linux is a harmless no-op (the Windows call itself is
  unverified).
- Static: version 0.4.0-rc6 consistent across app, UI, README, README.txt,
  CHANGELOG, SOURCE-NOTES and the .cmd launcher; no rc3 labels left in shipped
  files.

## Not tested

Real Windows launch of the bundled runtime and .cmd launcher, the real
SetThreadExecutionState behavior, the real Windows FolderBrowserDialog, real
ADB/USB driver behavior, real phones of any brand (including real toybox dd
semantics and exec-out throughput on large libraries), real wireless-debugging
pairing, Windows Task Scheduler registration, and restore into apps (out of
scope by design). rc1-rc3 suites covered the earlier features; their behavior
is unchanged except where listed in CHANGELOG.md.

## Before calling this stable

1. On a clean Windows 10/11 x64 PC, extract and start via
   START-megahy-backup.cmd. Try Browse...; the folder window should open in
   front of the browser.
2. Back up a small real folder over USB; check counts, dates and REPORT.txt.
3. Stop mid-run, click Start again with the same destination, choose Continue,
   and check the counts pick up where they stopped.
4. Stop inside a large video file, continue, and check the file plays and its
   manifest entry shows matching hashes.
5. Let the PC try to sleep during a run (it should stay awake); then close the
   lid on purpose, reopen, and continue the backup.
6. Repeat to see incremental skips; change one file and check it re-copies.
7. Try Wi-Fi pairing/connecting on an Android 11+ phone.
8. Try a small restore into /sdcard/ and check the files on the phone.
9. Create and run the scheduled task once by hand (schtasks) before relying on
   it.

Do not reset the phone based on these simulations.


megahy-backup 0.4.0-rc6, 23 November 2026

Fix: discover interrupted backups at launch and when the parent folder changes through typing, Browse or profile load. Continue requires scope acknowledgement and is invalidated immediately when the destination changes. Discovery does not start a backup or write its files. Backup engine/format unchanged from rc5.

Checks on Linux with synthetic ADB: 20 existing browser checks, 19 restart/discovery checks including the delivered rc5 failure and a report-only rc3 fixture, and 40 engine checks passed. No real Windows runtime, native dialog, keep-awake, USB or physical phone tested.

Use: close old console and tab, extract rc6 to a new app folder, run START-megahy-backup.cmd. Choose the PARENT containing the dated interrupted folder. Tick the scope box and press Continue. Do not start a new backup merely to enable Continue. If no interrupted offer appears, inspect the original folder/report instead. rc3 requires manifest.jsonl, inventory.json, and report.json with saved selection and an incomplete phase. Detection checks the ten newest dated folders.
