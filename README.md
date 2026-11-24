# megahy-backup

<img width="1917" height="4285" alt="image" src="https://github.com/user-attachments/assets/bc9503bc-a2ab-4e14-b06a-737597d7883a" />

*0.4.0-rc6 | Release candidate. New features tested in simulation only, not yet on a real phone.*
Selective Android backup for Windows PCs, by Marwan Megahy. Built with help from an AI assistant and tested by the author.

Copy readable photos, videos and other shared-storage files from any Android phone to your own PC over USB or Wi-Fi. Each verified file must have matching SHA-256 hashes on the phone before and after copying and on the PC. Contacts, SMS, MMS and call logs are optional best-effort exports, only when Android already permits access. Works the same on every phone brand; no brand-specific setup.

## Which PCs does it run on?

| PC | Status |
| --- | --- |
| Windows 10/11, Intel/AMD 64-bit | Intended packaged target. Python is included; no Python or pip installation is needed. |
| Windows ARM64 | Not validated. This is an x64 package, not a native ARM64 build. |
| 32-bit Windows or Windows 7/8/8.1 | Not supported by this release package. |
| macOS / Linux | No ready-to-run package included. The Python source is portable in principle, but needs that OS's Python and ADB plus testing. |

**Requirements:** one Android phone with USB debugging enabled (Developer options), a data cable, and Google's ADB. The app can download ADB (Platform-Tools) for you from Google on first run, or you can place the folder next to `START-megahy-backup.cmd` yourself. Some phones need the maker's official Windows ADB driver. No root, no phone app, no account.

Windows SmartScreen may warn about an unrecognized app because the package is not code-signed. The app is open source; check the code or the SHA-256 checksums, then choose "More info, Run anyway" if you trust it.

## Start on Windows

1. Extract the entire ZIP to a folder on your PC. Do not run it inside the ZIP.
2. Double-click `START-megahy-backup.cmd`. Keep its console open.
3. If ADB is missing, click "Download ADB automatically" in the setup card.
4. Connect one unlocked phone by USB and allow this PC, or use the Wi-Fi card (Android 11+ wireless debugging).
5. Choose a destination and scope, read the warning, then start.

Full instructions and report formats are in [README.txt](README.txt).

## Features

- All readable files, photos/videos by extension, one phone folder, or selected provider categories.
- **Incremental backup:** unchanged files verified in an earlier backup are skipped (size + date, or hash proof).
- **Continue an interrupted backup:** after Stop, a disconnect, an error, a crash or PC sleep, continue the same backup folder instead of starting over. Files already hash-verified are trusted as-is; everything else is copied and verified fresh.
- **Mid-file resume:** large files (4 MiB+) copy in 8 MiB ranged reads, so a stop inside a file keeps its verified chunks. The full SHA-256 check on phone and PC still gates every verified file.
- **Stays awake while copying:** the app asks Windows not to sleep during a run. Closing the lid, low battery or choosing Sleep yourself can still interrupt it; continue the backup afterwards.
- **One-click ADB setup:** downloads Google's Platform-Tools and checks the archive before installing.
- **Original dates kept:** copies carry the phone's modification time.
- **Wi-Fi backup:** pair and connect over wireless debugging (Android 11+).
- **Restore:** push verified files back to the phone into a dated folder, each hash re-checked.
- **Scheduled backups:** a Windows scheduled task runs unattended backups with your saved settings.
- **Profiles and saved settings:** your choices persist; save named profiles.
- **Dark mode and Arabic (RTL) interface.**
- Green hash-verified count, unchanged count, red failed count and a rough copy-time estimate.
- Pause/Resume within the current run. Stop ends it; partial files are never called verified.
- New dated output folder every run, per-file manifest, hashes, dates and category report.
- Free-space precheck before copying.
- Local browser interface on loopback with a random per-run token. No backup upload or analytics.

## Limits you must understand

This is a selected readable-file backup, not a full phone clone. Private app data, app chats, authenticator secrets, logins, eSIMs and settings are not extracted. Provider exports are archival, not tested restore backups. Read the in-app notice and REPORT.txt before trusting any reset decision. Incremental mode proves a file is unchanged by size and date or by hash, but like every incremental tool it can miss a change that keeps both identical; run a full backup when it matters.

## Testing status

0.4.0-rc6 passed 40 automated simulation checks (synthetic ADB device, Linux host): full backup, hash verification, stop-then-continue of the same folder, mid-file continue of a large file after a disconnect, corrupted-partial re-verification, whole-file fallback when ranged reads are unavailable, continuing an rc3-made interrupted folder, refusal to continue folders without selection proof, and re-copy of a verified file whose PC copy was deleted. The rc3 Browse picker fix is still verified by code inspection only and needs one real Windows PC check; the keep-awake request (SetThreadExecutionState) is likewise unverified on real Windows. Earlier candidates: rc3 passed 23 checks, rc2 passed 27, rc1 passed 39. **None of the features ran on a real phone or Windows PC yet.** See TESTING.md.

## License

GPLv3 or later. Copyright (c) 2026 Marwan Megahy. See LICENSE.txt, NOTICE.txt and THIRD-PARTY-NOTICES.md. Source: https://github.com/megahy/megahy-backup61

RC5 FIX: rc4 had a JavaScript syntax error that stopped every UI button. rc6 fixes it and adds headless browser interaction tests (20 passed), plus 40 engine simulations rerun. Close the old app console and browser tab, extract rc6 into a NEW app folder, then launch its START-megahy-backup.cmd. Keep your backup destination unchanged. Do not delete the old backup folders.


megahy-backup 0.4.0-rc6, 23 November 2026

Fix: discover interrupted backups at launch and when the parent folder changes through typing, Browse or profile load. Continue requires scope acknowledgement and is invalidated immediately when the destination changes. Discovery does not start a backup or write its files. Backup engine/format unchanged from rc5.

Checks on Linux with synthetic ADB: 20 existing browser checks, 19 restart/discovery checks including the delivered rc5 failure and a report-only rc3 fixture, and 40 engine checks passed. No real Windows runtime, native dialog, keep-awake, USB or physical phone tested.

Use: close old console and tab, extract rc6 to a new app folder, run START-megahy-backup.cmd. Choose the PARENT containing the dated interrupted folder. Tick the scope box and press Continue. Do not start a new backup merely to enable Continue. If no interrupted offer appears, inspect the original folder/report instead. rc3 requires manifest.jsonl, inventory.json, and report.json with saved selection and an incomplete phase. Detection checks the ten newest dated folders.
