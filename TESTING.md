# Candidate testing, 2026-11-22

Version: **0.3.1-rc2**. Simulations were run on 0.3.1-rc1; rc2 changes only the license, notices and version labels, with all 61 unit tests rerun and passing after the change. These are software simulation checks on Linux, not a Windows PC/VM, Android emulator, physical phone, USB connection or restore test. No Mac/Linux consumer build was made.

## Checks completed

- **61 automated unit/regression tests passed**, including six release-specific checks. Those cover missing ADB failing with help, the candidate report version, avoiding irrelevant missing-MIUI warnings, spaces/Arabic and a destination longer than 260 characters on the host filesystem, packaged x64 PE identification, and static Windows-launcher inspection. Static launcher inspection is not execution.
- **33 process/browser synthetic-device scenarios passed, 3,373 assertions/checks in total.** The real application process called a separate synthetic ADB process and generated synthetic files/providers. Cases included a 128 MiB file, Unicode and awkward names, case collisions, reserved Windows names, deep paths, denied providers, partial MMS, corrupted/changed copies, disconnects, full-disk error response, missing hash/find/stat commands, unauthorized connection, media/folder/provider selection, invalid paths, Pause/Resume, Stop while paused, unplug while paused and changed source while paused.
- Successful synthetic copies were independently compared with fixture source bytes. Corrupted/changed files were not marked verified. Full-disk and disconnect cases ended incomplete. Unselected providers were not queried.
- Chrome UI checks verified green success/red failure counters, live ETA behavior and paused-time exclusion. Desktop and 320/390-pixel layouts were captured; decisive desktop failure and narrow-screen completion screenshots were visually inspected for hierarchy, wrapping, status and copyright credit.
- The bundled runtime's **37 files matched the official CPython 3.14.10 Windows x64 embeddable ZIP byte-for-byte**, including its license notices. This is provenance comparison, not a Windows launch, signature verification or malware certification.
- Heuristic release audit passed: no bundled ADB/Platform-Tools, generated backup/report payloads, private-key blocks, personal Windows home paths or email addresses were found in the application text/package. Owner name and copyright credits are intentionally included. Synthetic names in test fixtures are not real contacts.

During testing, an old scenario assertion still expected the prior version string; the fixture was updated to the new version and all affected scenarios were rerun successfully. The initial broad run was time-limited after nine successful scenarios; the remaining five were run separately. No uncompleted or failed first pass was counted as a success.

- Fresh Windows-archive extraction into an Arabic/spaces path was launched using the Linux host interpreter, from a different working directory and with an empty command-search PATH. The actual Chrome UI correctly showed missing ADB and created no backup destination. This tested archive layout, source launch and the missing-tool error, not the Windows runtime or CMD launcher.

## Close-to-PC checks and limits

Spaces/Arabic paths and long paths were exercised on the Linux host filesystem. The Windows launcher quotes its local runtime and script paths, and the runtime is x64 PE. No Windows VM or Windows compatibility runtime was available. Therefore **the CMD launcher, Windows file-locking/long-path policy, USB drivers, no-installed-Python Windows startup and actual Windows security prompts remain unverified**. The presence and provenance of the included runtime explain why a separate Python install should not be required; they do not prove it ran on a clean Windows PC.

The original v0.3.0 package has a user-reported successful real run. That is separate from this candidate and does not establish compatibility with all Windows PCs or Android phones. Historic software checks are in TEST-RESULTS-v0.3.0.txt.

## Repeat the software checks

```text
python -m unittest discover -s tests -v
python tests/device_lab/run_lab.py --output /a/fresh/output/folder
python tests/device_lab/run_selected_lab.py --output /another/fresh/output/folder
python tools/audit_release.py
```

Process/browser fixtures require Linux, Playwright and Chrome/Chromium. Unit tests use Python's standard library. The source-only package skips the packaged-runtime test; the host long-path simulation test is skipped on Windows rather than claiming Windows policy support. The included GitHub Actions configuration is a proposal and has not been run on GitHub.

## Required before a stable Windows release

1. On a clean Windows 10/11 x64 account without a separate Python installation, extract into a path with spaces and a non-ASCII name. Double-click the launcher. First test with Platform-Tools absent, then add the official complete Google folder after reviewing its terms. Confirm the clear missing-runtime message using a deliberately incomplete separate extraction.
2. Connect a physical authorized Android phone with a working manufacturer driver. Copy a small selected folder containing known photos, videos, an empty file and Unicode/Windows-awkward filenames. Open representative files and compare hashes. Review every selected category's report.
3. Test Pause/Resume, Stop and a controlled cable disconnect using disposable test data and a fresh destination. Never risk the user's only copy or induce destructive disk failures on their main PC.
4. Check large files, enough free space, a safely constrained disposable destination, real Windows long paths, antivirus/SmartScreen behavior and an additional PC/driver combination. Do not bypass warnings to call the test successful.
5. Test restoration separately if any future restore/import claim is planned. No restore function or verified full-phone backup claim is part of this release.

Do not reset the phone based on these simulations.
