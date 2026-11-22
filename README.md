# megahy-backup
<img width="284" height="376" alt="image" src="https://github.com/user-attachments/assets/17198d0c-4aa4-45db-a30e-a13a44b9c1f4" />

*0.3.1-rc2 | Pre-release. Tested by the author on a real Windows PC and Android phone.*
Selective Android USB file backup for Windows PCs, prepared for Marwan Megahy.

Copy readable photos, videos and other shared-storage files to your own PC. Each verified storage file must have matching SHA-256 hashes on the phone before and after copying and on the PC. Contacts, SMS, MMS and call logs are optional best-effort exports, only when Android already permits access.

## Which PCs does it run on?

| PC | Status |
| --- | --- |
| Windows 10/11, Intel/AMD 64-bit | Intended packaged target. Python is included; no Python or pip installation is needed. Tested by the author on one Windows PC. |
| Windows ARM64 | Not validated. This is an x64 package, not a native ARM64 build. Do not promise compatibility. |
| 32-bit Windows or Windows 7/8/8.1 | Not supported by this release package. |
| macOS / Linux | No ready-to-run package included. The Python source is portable in principle, but requires a supported Python installation, that OS's official ADB, USB permissions and testing. The Windows launcher/runtime do not run natively there. |
| Locked-down school/work PC | May be blocked by policy, missing drivers or USB restrictions. Do not bypass your administrator's rules. |

"Any PC with no setup" would be misleading. **No Python install is needed**, but initial phone/ADB setup is still required. The app itself does not need a paid account, cloud account or phone app.

## Start on Windows

1. Extract the entire ZIP to a folder on your PC. Do not run it inside the ZIP.
2. Get **Windows SDK Platform-Tools directly from Google**: https://developer.android.com/tools/releases/platform-tools . Review and accept Google's terms yourself. Extract the complete `platform-tools` folder next to `START-megahy-backup.cmd`. Keep its files together. This package does not bundle or silently download Google's tools.
3. Enable ordinary USB debugging on your Android phone. Connect one unlocked phone with a data cable and accept this PC's debugging authorization. Settings vary by phone maker. Root, bootloader unlocking, factory reset and extra debugging-security toggles are not required.
4. If necessary, install only the phone maker's official Windows ADB USB driver. Links: https://developer.android.com/studio/run/oem-usb . A missing driver may require administrator help. Do not disable antivirus or install random driver packs.
5. Double-click `START-megahy-backup.cmd`. Keep its console open. Choose a backup destination and scope, read the warning, then start.

Full instructions and report formats are in [README.txt](README.txt).

## Features

- All readable files, photos/videos by extension, one phone folder, or selected provider categories.
- Green hash-verified file count, red failed count and a rough copy-time estimate.
- Pause/Resume within the current run. Pause waits for an operation to finish; keep the phone connected.
- Stop ends the run. A new run does not resume a stopped or closed run.
- New dated output folder every time, per-file manifest, hashes and category report.
- Local browser interface on loopback with a random per-run token. No backup upload or analytics.

## Limits you must understand

This is **not** a full phone clone, deleted-file recovery tool or safe-to-reset certificate. Hash verification proves copied bytes matched during transfer, not that every wanted file was found or that a file was healthy before copying. It cannot guarantee that every file will open or that every category can be restored.

The phone needs a working authorized ADB connection and readable shared storage. For file verification it must provide `sha256sum` and safe `find -print0` output. Missing capabilities fail safely rather than pretending to verify. Optional size measurement can be unavailable without stopping the copy.

Android may hide or deny app-private data, app chats, contacts/messages, secure folders, work profiles, cloud-only files, other users and some storage volumes. No permission bypass is attempted. Provider exports are archives and have not been restoration-tested. No iPhone support is included.

Do not erase or reset your phone based on this tool alone. Open important copied files and check the reports and your separate app/device backups. Backups and reports are **not encrypted** by this app. They may contain private filenames, messages, phone numbers and device identifiers. Protect the PC disk and do not upload reports publicly without redacting them. Disable USB debugging after use.

## Compatibility and testing

The previous v0.3.0 package had a user-reported successful real run. That is not a cross-PC or cross-phone certification, and this release candidate is a separate build. See [TESTING.md](TESTING.md) for this candidate's actual checks, remaining gaps and a repeatable Windows/phone checklist. Historic results remain in `TEST-RESULTS-v0.3.0.txt`.

## Copyright and license

Copyright (c) 2026 Marwan Megahy. megahy-backup is licensed under the **GNU General Public License version 3 or, at your option, any later version** (owner decision, 2026-11-22). See [LICENSE.txt](LICENSE.txt).

GPLv3 permits anyone to use, study, modify and share this software, including commercially, while requiring that distributed copies and derivative works carry the same license, copyright notices and corresponding source code. It does not surrender copyright. It does not guarantee enforcement, and no license can promise that nobody will misuse a name or remove a notice.

Code inherited from the original CableVault-credited preview remains under the MIT license; its notice is retained in [NOTICE.txt](NOTICE.txt), as MIT requires. The MIT license is compatible with GPLv3.

When the Windows package (an executable with a bundled Python runtime) is distributed, GPLv3 requires the corresponding source to be available. Distribute the source package **alongside** the Windows ZIP (same repository release or download page) and keep [NOTICE.txt](NOTICE.txt) and [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) with it.

Third-party Python components keep their own rights and notices. Google, Android, Python and device-maker names do not imply affiliation or endorsement. See [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

This private candidate does not authorize publication. The owner has approved the GPLv3 license and attribution; publication destination and timing remain his decision. This is release preparation, not legal advice.

## Development

The application uses Python's standard library. From the source folder on a development machine:

```text
python -m unittest discover -s tests -v
python megahy_backup.py --no-browser
```

The process/browser fixture suite is Linux-only test infrastructure. It generates synthetic data, not a real phone. Follow `tests/device_lab/README.txt`. Never put the synthetic `adb` fixture on the PATH for a real backup.

For a future GitHub repository, upload the source package, not personal backups or generated test results. See [RELEASE-CHECKLIST.md](RELEASE-CHECKLIST.md).
