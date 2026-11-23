# Candidate testing, 2026-11-23

Version: **0.4.0-rc3**. All checks are software simulations on Linux with a
synthetic ADB process and a mirror phone filesystem. **No real phone, real ADB,
real USB cable, real Wi-Fi link, Windows PC or Windows Task Scheduler ran this
candidate.** Treat Wi-Fi pairing, scheduling and restore as untested on hardware.

## The two rc3 changes

1. In-app notice: the sentence about the earlier user-reported run and
   simulation-only testing was removed (owner request), in English and Arabic.
   Static checks confirm the sentence is gone from both languages and the rest
   of the notice is unchanged.
2. Browse... folder picker now opens owned by an invisible top-most window, so
   it appears in front of the browser instead of behind it (owner-reported rc2
   bug). **Not confirmed on real Windows yet**: PowerShell's
   FolderBrowserDialog does not exist on Linux, so the generated command was
   verified by inspection only (top-most owner form, handle creation,
   disposal). The non-Windows fallback error still works. Confirm on a real
   Windows PC before calling this fixed.

## What passed (23 checks, 2026-11-23)

End-to-end through the real backup engine and HTTP API with a synthetic ADB:
- Full backup of a 5-file simulated phone (including an Arabic filename): all
  files hash-verified, zero failures.
- Photo modification dates preserved on the PC copies (exact mtime match).
- Incremental run 2: all 5 files skipped as unchanged, none re-copied; the
  manifest records skipped-unchanged and names the folder holding the bytes.
- Changed file (different size): exactly that file re-copied, others skipped.
- Changed file (same size, different content): hash comparison caught it and
  re-copied it. A change keeping size AND date identical would be skipped; this
  is documented in the UI and README.
- Incremental off: full re-copy of all files.
- Wi-Fi: pair, connect, and a photos-only backup over the simulated Wi-Fi
  serial; bad pairing codes and invalid hosts/ports rejected.
- Restore: all 5 verified files pushed back into a dated phone folder, each
  SHA-256 re-verified on the phone side, restore manifest written.
- Provider categories (contacts, SMS, MMS, call log): when the simulated phone
  returns no records, the run completes cleanly and reports zero records.
- Headless --auto mode (the scheduled command): finds platform-tools/adb next
  to the app, runs a full backup, writes last-auto-run.json.
- Local API: per-run token required (403 without it), loopback Host enforced,
  UI served, /api/browse-folder returns the documented fallback error on
  non-Windows, start requires the scope acknowledgement, unknown actions 404.
- Unit-level: host/port validation, selection validation and exclusion rules,
  NameMapper path safety (reserved names, `..` rejected, case collisions
  split), settings round-trip and corrupt-file fallback, scheduler time
  validation and honest non-Windows refusal.
- Static: version 0.4.0-rc3 consistent across app, UI, README, README.txt,
  CHANGELOG, SOURCE-NOTES and the .cmd launcher; notice text changed as
  requested; the picker's top-most owner present in the generated command.

## Not tested

Real Windows launch of the bundled runtime and .cmd launcher, the real Windows
FolderBrowserDialog (the rc3 front-of-browser fix in particular), real ADB
driver behavior, real phones of any brand, real wireless-debugging pairing,
Windows Task Scheduler registration, very large files and libraries, and
restore into apps (out of scope by design).

## Before calling this stable

1. On a clean Windows 10/11 x64 PC, extract and start via
   START-megahy-backup.cmd. Try the Browse... button: the folder window should
   open in front of the browser, not behind it.
2. Back up a small real folder over USB; check counts, dates and REPORT.txt.
3. Repeat to see incremental skips; change one file and check it re-copies.
4. Try Wi-Fi pairing/connecting on an Android 11+ phone.
5. Try a small restore into /sdcard/ and check the files on the phone.
6. Create and run the scheduled task once by hand (schtasks) before relying on it.

Do not reset the phone based on these simulations.
