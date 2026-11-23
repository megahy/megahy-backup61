megahy-backup 0.4.0-rc3
RELEASE CANDIDATE. New features are simulation-tested only.
Start with README.md for supported PCs, rights and current test status.

SETUP ONCE
1. Extract the entire ZIP into a new folder on a 64-bit Intel/AMD Windows 10/11
   PC. Open the extracted folder containing START-megahy-backup.cmd, ui.html,
   megahy_backup.py and runtime. Do not run it from inside the ZIP.
2. Add Google's ADB (Platform-Tools). Easiest: start the app and click
   "Download ADB automatically"; it downloads the official ZIP from Google,
   checks it and installs it next to the app. Manual alternative: download
   https://developer.android.com/tools/releases/platform-tools yourself,
   accept Google's terms and extract the whole platform-tools folder next to
   START-megahy-backup.cmd. Keep adb.exe and its accompanying DLLs together.
   A separate Python install is not needed.
3. On the phone, enable Developer options and ordinary USB debugging. The exact Settings labels vary by phone maker; use its official instructions. Use a data cable,
   unlock the phone and accept this PC's USB debugging authorization.
   Leave Install via USB, debugging security/input-control toggles and OEM
   unlocking alone. This read-only app does not need them.
4. Connect only one USB phone. If ADB cannot see it, check the cable, authorization
   and the manufacturer's Windows ADB driver. Seeing files in Explorer is not
   proof that the ADB driver is installed. Do not disable antivirus or install
   random driver packs. If security software blocks the app, keep the exact
   warning for troubleshooting rather than disabling protection.
5. Double-click START-megahy-backup.cmd and keep its console window open.

CHOOSE WHAT TO COPY
- Everything readable: all discovered readable regular files in primary shared
  storage and recognized mounted SD cards, plus all four provider attempts.
- Photos / videos: common filename extensions, case-insensitive. This is not a
  content scan. Missing/unusual extensions can be missed, and an unrelated file
  with a media extension can be included. These choices do not request providers
  unless you select their checkboxes. Photo/video bytes are not converted.
- SMS / Contacts / MMS / Call log only: no shared-storage scan, file hashing or
  file pull. Only the selected provider is queried. Android may still deny it.
- One phone folder: enter an absolute phone path, for example
    /sdcard/DCIM/Camera
    /sdcard/Download
    /storage/ABCD-1234/DCIM
  Subfolders are included. /storage/emulated/0/ is accepted as /sdcard/.
  Private paths, Windows PC paths and .. traversal segments are refused.
  The folder must exist and be readable. For folder names with spaces or an
  apostrophe, enter the normal path without adding shell quotes.
- Custom selections: choose a storage mode and any combination of providers.
  At least one storage/provider category must be selected.

HIDDEN AND CACHE SWITCHES
"Include hidden files and folders" starts checked. Uncheck it to skip a path
when any component starts with a dot, such as .privacy or .nomedia. This does not
mean those files are unimportant. A specifically chosen hidden folder also
needs this Include switch left checked if you want its contents.

"Include common cache / thumbnail folders" also starts checked. Uncheck it to
skip folders named cache, caches, .cache, code_cache, thumbnails or .thumbnails,
case-insensitive. Only whole folder names match. This is a name heuristic, not
a claim that files are safe to discard. Photos or wanted files may be inside.

These switches only exclude data from this backup. They never delete, clean or
free space on the phone. Filtering may still list all readable paths to decide
what to exclude; it need not speed up the initial scan. Excluded file contents
are not pulled or hashed. Check Scanned versus Selected files and the report.

START, PAUSE, RESUME, STOP
1. Check the green selection summary and choose a PC destination. The default is
   the megahy-backup folder inside your Windows user folder. A fresh dated
   megahy-backup-YYYYMMDD-HHMMSS-random folder is created on every run.
2. Tick the scope notice and click Start selected backup. Keep the phone idle,
   connected and unlocked. Selection controls stay locked while the run is open.
3. Pause asks the app to wait between device operations. "Pausing safely" means
   the current ADB operation is still finishing. A large pull or hash can take
   time. Only "Paused" means no next device operation will start until Resume.
   A file copied but not fully checked stays .partial and is not counted verified.
4. Keep the cable connected while paused. Pause is NOT permission to unplug.
   Resume checks the pinned device again. If it is unavailable, the run ends
   incomplete; reconnect and start a new run. If the same phone was reconnected
   and is available, pending reads can continue, but changed files can fail
   their hashes. Earlier copies are not revalidated as a phone-wide snapshot.
5. Resume continues only this still-open running session. It does not resume
   after closing the console, rebooting, an error or Stop. For repeat backups,
   use Incremental mode instead: unchanged files are skipped.
6. Stop ends the current run, including while paused. Already verified files
   remain. In-flight files are not called verified. A later Start creates a new
   backup; it does not continue the stopped one.

COPY TIME LEFT IS AN ESTIMATE
After scanning, the app optionally measures selected file sizes in batches.
This adds preparation time, especially for large selections. It does not hash or
pull excluded files. If stat is missing or sizes cannot be measured, copying
continues and the display states that some sizes are unknown.

The copy estimate learns from this run's completed-file rate and verified-byte
rate, using the slower remaining-time estimate. There is no fixed files/minute
assumption. Pause time is excluded. At first it says Estimating; tiny samples
are not used to predict a large remaining byte volume. The estimate can move
up or down a lot as file sizes, errors, hashing time and transfer speed change.
It is not a promise of when the whole backup will finish. Scanning, provider
reads, size preparation and final rescan/report time are outside this copy ETA.
Provider-only runs have no reliable countdown. Keep the phone connected until
the run actually ends, not merely until an estimated time passes.

WHEN IT IS DONE
- "Finished with gaps" is the normal completed selected-run phase. It always
  retains the warning that this is not a full-phone or safe-to-reset backup.
- "Stopped, incomplete" means Stop ended the run early.
- "Error, incomplete" means a requested operation failed, no selected data was
  exported, the phone became unavailable, a required tool was missing, etc.
- Read REPORT.txt and category-report.json, not only the counters. A category
  can be unavailable even if storage files copied. A provider-only run normally
  has zero Selected files / Hash verified files because its provider rows are
  counted separately. "Not selected" is not a permission failure.
- Open backup folder is enabled only after the worker and final report finish.
  An incomplete run still has a folder to inspect when report writing succeeded.

WHAT IS SAVED
files/Internal storage/... and files/SD-XXXX-XXXX/...
  Verified original file bytes. Full volume-relative paths are kept even for a
  one-folder selection. Windows-incompatible names and case collisions are
  safely mapped; manifest.jsonl records the source-to-local mapping. Windows
  may need a codec to open an unusual original media format.
automatic-exports/category-report.json
  Requested categories show exported (not restore-tested), partial, unavailable,
  or incomplete. Unrequested categories show not selected. During a run the UI
  can show pending or reading. An interrupted provider is marked incomplete.
automatic-exports/contacts/contacts.vcf
  Provider-visible contact vCards only. Other profiles, SIM-only, filtered or
  cloud-only contacts may be absent. A permission denial is not bypassed.
automatic-exports/sms/ and call-log/
  JSON plus convenience CSV. JSON preserves original nulls, multiline/Unicode
  text and control characters. CSV formula-like text is apostrophe-prefixed;
  NUL is displayed as the visible escape \u0000. JSON is the archival source.
automatic-exports/mms/
  Message metadata, per-message addresses, part metadata/text, binary attachment
  files and an attachment index. RCS and app-specific chats are not promised.
REPORT.txt / report.json / inventory.json / manifest.jsonl
source-sizes-reference.json (optional measured sizes for the ETA, not a snapshot)
  Selection, counts, warnings, selected source paths and per-file copy/hash
  results. Source hashes before and after copying must match the PC file hash
  before a storage file is marked verified. Provider exports do not have this
  source-versus-PC checksum/completeness proof.

NEW IN 0.4.0
- Incremental backup (on by default): skips files proven unchanged since an
  earlier verified backup in the same destination. Proof is size+modification
  time, or a SHA-256 match when timestamps are unavailable. Skipped files are
  not re-copied; the manifest names the earlier folder that holds them. A change
  that keeps size and date identical can be missed, as with any incremental tool.
- Original file dates: verified copies carry the phone's modification time.
- Wi-Fi (Android 11+): Developer options, Wireless debugging. Pair once with
  the pairing IP/port/code, then Connect with the connect port. USB is unchanged.
- Restore: copies verified files of a chosen backup into a dated folder on the
  phone and re-verifies each hash. It does not restore app data, contacts or
  messages into their apps, and it writes to the phone (backups never do).
- Scheduled backups: creates a Windows Task Scheduler entry that runs
  "megahy_backup.py --auto" with your saved settings. The phone must be
  connected and authorized at that time. Remove it any time from the app.
- Profiles, dark mode, Arabic interface, free-space precheck.

STILL NOT EXTRACTED
Private app data, installed apps, app logins/passwords, authenticator secrets,
WhatsApp/Signal app chat databases, accounts, eSIMs and system settings. Work
profiles, secure folders, other users, cloud-only and unreadable files may be
absent. Provider archives are not
promised Android/Xiaomi-importable backups. No restoration has been tested.

PRIVACY AND SAFETY
The app reads only. No push/install/grant/provider write/delete/reset is issued.
It binds to 127.0.0.1 with a random per-run token and does not upload backups or
send analytics. Keep that local console URL private. Backup data, reports and
filenames are not encrypted; protect your PC disk. Disable USB debugging when
finished. Keep enough disk space; a recognized full-disk ADB error aborts the run.

TESTING
0.4.0-rc3: 23 automated checks passed on Linux with a synthetic ADB device,
re-running the core backup suite plus the two rc3 changes (see TESTING.md).
The Browse picker front-of-browser fix is verified by code inspection only and
awaits a real Windows PC. rc2 had 27 checks; rc1 had 39. Historic v0.3.0: 55
automated regression tests and 33 scenario checks. These are software
simulations, not a real phone success rate.
Tests ran on Linux/Python 3.10.12 with a separate synthetic ADB command process.
The new Windows runtime/launcher, real ADB/USB, real Android providers,
phone completeness, multi-GB files, huge libraries and restoration are untested.
The ZIP includes source and test fixtures, not generated synthetic datasets.

SOURCES
https://developer.android.com/tools/adb
https://developer.android.com/tools/releases/platform-tools
https://developer.android.com/studio/run/oem-usb
https://developer.android.com/reference/android/provider/ContactsContract.Contacts
https://developer.android.com/reference/android/provider/Telephony.Sms
https://developer.android.com/reference/android/provider/Telephony.Mms.Part
https://developer.android.com/reference/android/provider/CallLog.Calls
https://www.python.org/downloads/release/python-31410/

