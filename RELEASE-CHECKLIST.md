# Before public release

This candidate is private. No repository, release, public share or public download was created.

## Owner decisions
- [x] License approved by owner on 2026-11-22: GPLv3-or-later, with the Marwan Megahy copyright credit and the retained CableVault MIT attribution in NOTICE.txt.
- [ ] Confirm you have the right to release the application material. No audit can create rights you do not have.
- [ ] Choose a GitHub account/repository and approve publication. Do not insert private contact details merely to fill a template.
- [ ] Approve the honest target: Windows 10/11 Intel/AMD x64, Android via ADB. Not every PC, not iPhone, not a full-phone backup.

## Validation before calling it stable
- [ ] Extract the Windows ZIP into a fresh ordinary Windows 11 x64 account with no separately installed Python.
- [ ] Download Platform-Tools through Google's terms page, authorize one physical Android phone and perform the TESTING.md checklist.
- [ ] Repeat on Windows 10 x64 if support for it is claimed. Observe OS security-support limits; this package does not extend Microsoft's support.
- [ ] Check a large file, non-ASCII names, permission denial, a full disk, cable disconnect, Pause/Resume and Stop on real hardware.
- [ ] Open representative copied files, compare hashes, inspect reports and verify no reset/full-backup promises appear.
- [ ] Test on more PC/phone/driver combinations before broad compatibility claims.
- [ ] Run the included unit tests and synthetic process/browser suites, and preserve their actual results. CI configuration included here is not proof that GitHub Actions ran.

## Repository and release hygiene
- [ ] Use the source-only ZIP as the repository starting point. Keep `.gitignore`, notices, source and tests. Do not commit `runtime`, `platform-tools`, backups, generated reports or local tokens.
- [ ] Keep LICENSE.txt (GPLv3), NOTICE.txt (retained MIT notice) and third-party notices at the root; retain all existing upstream notices with runtime distributions.
- [ ] GPLv3 source obligation: publish the matching source package alongside every distributed Windows binary (same release page or repository). Do not distribute the binary ZIP alone.
- [ ] Replace any future support placeholders with approved details. The current docs deliberately do not invent a repository URL or email.
- [ ] Run `python tools/audit_release.py` and inspect its results. It is a heuristic, not a secrets scanner or legal certification.
- [ ] Rebuild release archives with `python tools/build_release.py --output /your/output/folder`; verify archive SHA-256 values in a separate checksum file.
- [ ] Review the final source diff and exact ZIP contents, then approve publication. Never include this private owner-review document in a public release by accident.

Do not sign software with an invented certificate or tell users to bypass SmartScreen/antivirus. Signing would require an approved identity/certificate and its own cost decision.
