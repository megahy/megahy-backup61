# Copyright (c) 2026 Marwan Megahy
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License version 3 or (at your option) any later
# version. See LICENSE.txt.
"""megahy-backup 0.4.0-rc3. Standard-library-only Android backup for Windows PCs."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import http.server
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser

# Support the bundled isolated Windows interpreter and source execution.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import selection
import settings as app_settings
import adbtools
import scheduler
from eta import CopyProgress

# Keep cancellation types identical when launched as a script.
sys.modules.setdefault('megahy_backup', sys.modules[__name__])
BASE = Path(__file__).resolve().parent
VERSION = '0.4.0-rc3'
GAPS = [
    'This is a file backup, not a full phone clone or a reset-safety certificate.',
    'Private app data, installed apps, logins, passwords, authenticator secrets, WhatsApp/Signal chats, system settings and eSIMs are not extracted. Contacts, SMS, MMS and call-log provider exports are attempted only when the Android shell is already allowed to read them.',
    'Automatic provider exports can be denied by Android. Contacts use provider vCards when available. SMS/call logs use JSON and CSV; MMS uses JSON and binary parts. These are archival exports, not tested Android-restorable backups. Provider visibility does not prove completeness.',
    'Cloud-only photos, locked/secure folders, work profiles, other users and unmounted or unusually named storage volumes may be missing.',
    'Android may deny access or hide files from the shell even inside shared storage. Unreadable files may be absent. Empty directories are not copied.',
    'Only the chosen categories and folders are attempted. Media filters use filename extensions, not content. Hidden/cache exclusions may omit wanted files; they never delete or free space on the phone.',
    'A live phone is not a snapshot. Stop using it during backup, then check important files and each app backup before considering a reset.',
    'Incremental mode skips files whose size and modification time (or content hash) match an earlier verified backup in the same destination. It cannot detect every possible change; when in doubt, run with incremental off.',
    'Backups are not encrypted by this app. Protect the backup disk. Restore copies verified files back to a phone folder you choose; it does not restore app data, contacts, messages or settings into their apps.'
]

class BackupError(Exception):
    pass

class Cancelled(BackupError):
    pass

class DeviceDisconnected(BackupError):
    pass


def local_path(p):
    p = os.path.abspath(p)
    if os.name == 'nt' and not p.startswith('\\\\?\\'):
        return '\\\\?\\UNC\\' + p[2:] if p.startswith('\\\\') else '\\\\?\\' + p
    return p


def digest(path):
    h = hashlib.sha256()
    with open(local_path(path), 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


class NameMapper:
    """Stable, collision-aware mapping into Windows-compatible filenames."""
    def __init__(self):
        self.paths = {}
        self.used = set()

    def map(self, rel):
        parts = PurePosixPath(rel).parts
        if not parts or any(p in ('..', '/', '') for p in parts):
            raise BackupError('Unsafe relative path rejected')
        mapped = []
        for i, part in enumerate(parts):
            prefix = '/'.join(parts[:i+1])
            if prefix in self.paths:
                mapped.append(self.paths[prefix])
                continue
            name = re.sub(r'[<>:"/\\|?*\x00-\x1f%]', lambda m: '%%%02X' % ord(m[0]), part)
            while name.endswith((' ', '.')):
                name = name[:-1] + ('%20' if name[-1] == ' ' else '%2E')
            if re.match(r'^(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\.|$)', name, re.I):
                name = '_' + name
            if len(name) > 100:
                name = name[:75] + '~' + hashlib.sha256(part.encode('utf-8')).hexdigest()[:16]
            key = '/'.join(mapped + [name]).casefold()
            if key in self.used:
                name += '~' + hashlib.sha256(prefix.encode('utf-8')).hexdigest()[:16]
                key = '/'.join(mapped + [name]).casefold()
            if key in self.used:
                raise BackupError('Filename collision could not be resolved')
            self.used.add(key)
            self.paths[prefix] = name
            mapped.append(name)
        return Path(*mapped)


HOST_RE = re.compile(r'^[0-9A-Za-z]([0-9A-Za-z.\-]{0,251}[0-9A-Za-z])?$')


def validate_host_port(host, port):
    if not isinstance(host, str) or not HOST_RE.fullmatch(host):
        raise ValueError('Enter a valid phone IP address or host name')
    try:
        port = int(port)
    except (TypeError, ValueError):
        raise ValueError('Enter a valid port number')
    if not 1 <= port <= 65535:
        raise ValueError('Port must be between 1 and 65535')
    return host, port


def pick_folder():
    """Open the Windows folder picker and return the chosen path.

    Returns '' when the user cancels the dialog. Raises BackupError when no
    picker is available, so the caller can fall back to typing the path.
    """
    if os.name != 'nt':
        raise BackupError('The folder picker is only available on Windows. Type the folder path instead.')
    command = (
        'Add-Type -AssemblyName System.Windows.Forms;'
        '[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;'
        "$d=New-Object System.Windows.Forms.FolderBrowserDialog;"
        "$d.Description='Choose the folder where your backups are kept';"
        '$d.ShowNewFolderButton=$true;'
        # An invisible top-most owner window keeps the picker in front of the
        # browser window; in rc2 it could open behind it (owner-reported).
        '$o=New-Object System.Windows.Forms.Form;'
        '$o.TopMost=$true;'
        '$o.ShowInTaskbar=$false;'
        '$h=$o.Handle;'
        '$r=$d.ShowDialog($o);'
        '$o.Dispose();'
        'if($r -eq [System.Windows.Forms.DialogResult]::OK){[Console]::Out.Write($d.SelectedPath)}'
    )
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-STA', '-Command', command],
            capture_output=True, timeout=600,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except (OSError, subprocess.TimeoutExpired) as e:
        raise BackupError('The folder picker could not open. Type the folder path instead.') from e
    if result.returncode != 0:
        raise BackupError('The folder picker could not open. Type the folder path instead.')
    path = result.stdout.decode('utf-8', 'replace').strip()
    if path and not re.fullmatch(r'[^\x00-\x1f]*', path):
        raise BackupError('The folder picker returned an unreadable path. Type the folder path instead.')
    return path


class Engine:
    def __init__(self, adb=None):
        self.adb = adb
        self.serial = None
        self.wireless = False
        self.options = selection.defaults()
        self.progress = CopyProgress()
        self.stop = threading.Event()
        self.resume_gate = threading.Event()
        self.resume_gate.set()
        self.resume_check = False
        self.lock = threading.Lock()
        self.previous = {}
        self.state = dict(phase='Ready', detail='Connect one unlocked Android phone by USB, or use Wi-Fi.',
                          running=False, mode='backup',
                          total=0, done=0, verified=0, failed=0, skipped=0, vcf=0, folder='',
                          warnings=[], recent=[], categories={}, scanned=0, excluded=0,
                          paused=False, pause_requested=False, selection=selection.defaults(),
                          adb_setup=None)

    def update(self, **kw):
        with self.lock:
            self.state.update(kw)

    def snapshot(self):
        with self.lock:
            result = json.loads(json.dumps(self.state))
        result.update(self.progress.snapshot())
        return result

    def warn(self, text):
        with self.lock:
            self.state['warnings'].append(text)

    def request_pause(self):
        with self.lock:
            if not self.state['running']:
                raise ValueError('No backup is running')
            self.state['pause_requested'] = True
            self.resume_gate.clear()

    def resume(self):
        with self.lock:
            if not self.state['running'] or not self.state['pause_requested']:
                raise ValueError('No paused or pausing backup to resume')
            self.state['pause_requested'] = False
            self.resume_gate.set()

    def request_stop(self):
        self.stop.set()
        self.resume_gate.set()
        self.update(pause_requested=False)

    def wait_ready(self):
        if self.stop.is_set():
            raise Cancelled('Stopped by user')
        if not self.resume_gate.is_set():
            self.progress.pause()
            self.update(paused=True)
            try:
                while not self.resume_gate.wait(.1):
                    if self.stop.is_set():
                        raise Cancelled('Stopped by user')
                if self.stop.is_set():
                    raise Cancelled('Stopped by user')
                self.resume_check = True
            finally:
                self.progress.resume()
                self.update(paused=False)

    def run(self, args, timeout=120, device=True):
        self.wait_ready()
        if self.resume_check:
            self.resume_check = False
            if self.serial:
                code, out, _ = self.invoke(['get-state'], timeout=15)
                if code or out.strip() != b'device':
                    raise DeviceDisconnected('Phone unavailable after Pause. This run is incomplete. Reconnect and start a new run; no partial file is verified.')
        return self.invoke(args, timeout=timeout, device=device)

    def invoke(self, args, timeout=120, device=True):
        if self.stop.is_set():
            raise Cancelled('Stopped by user')
        cmd = [self.adb] + (['-s', self.serial] if device and self.serial else []) + list(args)
        # No host shell. Remote shell commands use fixed syntax and shlex-quoted paths.
        with __import__('tempfile').TemporaryFile() as out, __import__('tempfile').TemporaryFile() as err:
            p = subprocess.Popen(cmd, stdout=out, stderr=err,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            deadline = time.monotonic() + timeout
            while p.poll() is None:
                if self.stop.is_set() or time.monotonic() > deadline:
                    p.kill()
                    p.wait()
                    if self.stop.is_set():
                        raise Cancelled('Stopped by user')
                    raise BackupError('ADB timed out. Check the connection and phone; this run is incomplete.')
                time.sleep(.08)
            out.seek(0)
            err.seek(0)
            return p.returncode, out.read(), err.read()

    def shell(self, command, timeout=120):
        return self.run(['shell', command], timeout=timeout)

    def ensure_adb(self):
        if not self.adb:
            found = adbtools.find_adb(BASE)
            if not found:
                raise BackupError('ADB not found. Use "Download ADB automatically" in the setup card, or place Google Platform-Tools next to START-megahy-backup.cmd. See README.txt.')
            self.adb = found
        return self.adb

    def setup_adb_async(self):
        """Download and install Google Platform-Tools in the background."""
        with self.lock:
            if self.state.get('adb_setup') and self.state['adb_setup'].get('stage') in ('downloading', 'installing'):
                raise ValueError('ADB setup is already running')
        def work():
            try:
                def progress(percent, stage):
                    self.update(adb_setup={'stage': stage, 'percent': percent, 'error': None})
                adb = adbtools.download_and_install(BASE, progress)
                self.adb = adb
                self.update(adb_setup={'stage': 'ready', 'percent': 100, 'error': None})
            except Exception as e:
                self.update(adb_setup={'stage': 'error', 'percent': None, 'error': str(e)})
        threading.Thread(target=work, daemon=True).start()
        return True

    def pair_wifi(self, host, port, code):
        """Android 11+ wireless debugging pairing. Untested on real hardware."""
        host, port = validate_host_port(host, port)
        if not isinstance(code, str) or not re.fullmatch(r'\d{6}', code.strip()):
            raise ValueError('Enter the 6-digit pairing code shown on the phone')
        self.ensure_adb()
        rc, out, err = self.invoke(['pair', host + ':' + str(port), code.strip()], timeout=60, device=False)
        text = (out + err).decode('utf-8', 'replace')
        if rc or 'success' not in text.lower():
            raise BackupError('Pairing failed: ' + text.strip()[:400])
        return True

    def connect_wifi(self, host, port):
        """Connect to a phone over Wi-Fi (wireless debugging). Untested on real hardware."""
        host, port = validate_host_port(host, port)
        self.ensure_adb()
        rc, out, err = self.invoke(['connect', host + ':' + str(port)], timeout=60, device=False)
        text = (out + err).decode('utf-8', 'replace').lower()
        if rc or 'connected' not in text or 'cannot' in text or 'failed' in text or 'refused' in text:
            raise BackupError('Wi-Fi connect failed: ' + (out + err).decode('utf-8', 'replace').strip()[:400])
        self.serial = host + ':' + str(port)
        self.wireless = True
        return self.serial

    def connect(self):
        self.ensure_adb()
        if self.wireless and self.serial:
            code, out, err = self.run(['devices'], device=False)
            listing = out.decode('utf-8', 'replace')
            if code or not re.search(r'^' + re.escape(self.serial) + r'\s+device\s*$', listing, re.M):
                self.wireless = False
                self.serial = None
                raise BackupError('The Wi-Fi phone is no longer connected. Reconnect it from the Wi-Fi card, or plug in USB.')
        else:
            code, out, err = self.run(['-d', 'get-serialno'], device=False)
            serial = out.decode('utf-8', 'replace').strip()
            if code or not serial or serial == 'unknown':
                raise BackupError('Connect exactly ONE USB phone, unlock it and accept Allow USB debugging. If it is still missing, check the cable and manufacturer USB driver. ADB: ' + err.decode('utf-8', 'replace')[:400])
            self.serial = serial
        code, out, _ = self.shell('getprop ro.product.model')
        model = out.decode('utf-8', 'replace').strip() if not code else 'Android phone'
        _, version, _ = self.shell('getprop ro.build.version.release')
        return dict(model=model, android=version.decode('utf-8', 'replace').strip(), serial=self.serial)

    def roots(self):
        roots = [('Internal storage', '/sdcard/')]
        code, out, err = self.shell('ls /storage')
        if code:
            self.warn('Could not enumerate additional storage volumes. Only /sdcard/ will be attempted.')
        else:
            for name in out.decode('utf-8', 'replace').splitlines():
                if re.fullmatch('[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}', name):
                    roots.append(('SD-' + name, '/storage/' + name + '/'))
                elif name not in ('emulated', 'self'):
                    self.warn('Unrecognized storage entry not automatically copied: ' + name)
        return roots

    def inventory(self, root):
        code, out, err = self.shell('find ' + shlex.quote(root) + ' -type f -print0', timeout=900)
        if out and not out.endswith(b'\0'):
            raise BackupError('This phone cannot provide a safe NUL-delimited file listing. No unsafe filename fallback is used.')
        if code or err.strip():
            self.warn('Scan warnings for ' + root + ': ' + err.decode('utf-8', 'replace')[:3000])
        if code and not out:
            raise BackupError('Could not scan ' + root + '. This phone may lack find -print0 or storage access.')
        paths = []
        for raw in out.split(b'\0'):
            if not raw:
                continue
            try:
                path = raw.decode('utf-8')
            except UnicodeError:
                self.warn('A non-UTF-8 filename was skipped under ' + root)
                continue
            if not path.startswith(root) or '..' in PurePosixPath(path[len(root):]).parts:
                self.warn('Unexpected path was rejected under ' + root)
                continue
            paths.append(path)
        return sorted(set(paths))

    def remote_hash(self, path):
        code, out, err = self.shell('sha256sum ' + shlex.quote(path), timeout=7200)
        if code:
            raise BackupError('Cannot hash source file: ' + err.decode('utf-8', 'replace')[:400])
        match = re.match(rb'\\?([0-9a-fA-F]{64})(?:\s|$)', out)
        if not match:
            raise BackupError('Phone returned an unrecognized SHA-256 result')
        return match[1].decode().lower()

    def measure_meta(self, inventory):
        """Optional size and modification-time metadata for ETA, incremental mode and
        date preservation. Batches avoid an extra PC subprocess per file."""
        sizes = {remote: None for _, _, remote in inventory}
        mtimes = {remote: None for _, _, remote in inventory}
        batches = []
        batch = []
        length = 0
        for _, _, remote in inventory:
            quoted = shlex.quote(remote)
            if batch and (len(batch) >= 64 or length + len(quoted) > 6000):
                batches.append(batch)
                batch = []
                length = 0
            batch.append(remote)
            length += len(quoted) + 1
        if batch:
            batches.append(batch)
        failures = 0
        for index, batch in enumerate(batches, 1):
            self.update(detail='Measuring selected file sizes: batch ' + str(index) + ' of ' + str(len(batches)))
            try:
                code, out, err = self.shell("stat -c '%s %Y' -- " + ' '.join(shlex.quote(p) for p in batch), timeout=900)
                lines = out.decode('ascii').splitlines()
                if code or err.strip() or len(lines) != len(batch) or any(not re.fullmatch(r'[0-9]+ [0-9]+', line) for line in lines):
                    failures += 1
                    if code == 127 or failures >= 5:
                        break
                    continue
                for remote, line in zip(batch, lines):
                    size, mtime = line.split(' ')
                    sizes[remote] = int(size)
                    mtimes[remote] = int(mtime)
            except (Cancelled, DeviceDisconnected):
                raise
            except Exception:
                break
        unknown = sum(n is None for n in sizes.values())
        if unknown:
            self.warn('Could not measure ' + str(unknown) + ' selected file sizes. Backup can continue; the rough ETA, incremental matching and date preservation have incomplete information.')
        return sizes, mtimes

    def load_previous(self, destination, current_name):
        """Newest-first map of source path -> verified record from earlier backups in
        the same destination. Used only when incremental mode is on."""
        self.previous = {}
        try:
            candidates = sorted((p for p in Path(destination).glob('megahy-backup-*') if p.is_dir() and p.name != current_name),
                                key=lambda p: p.name, reverse=True)
        except OSError:
            return
        used = 0
        for cand in candidates[:5]:
            manifest = cand / 'manifest.jsonl'
            if not manifest.is_file():
                continue
            try:
                with open(manifest, encoding='utf-8') as f:
                    for line in f:
                        try:
                            record = json.loads(line)
                        except ValueError:
                            continue
                        if record.get('status') not in ('verified', 'skipped-unchanged'):
                            continue
                        source = record.get('source')
                        if not isinstance(source, str) or source in self.previous:
                            continue
                        self.previous[source] = dict(
                            bytes=record.get('bytes'),
                            mtime=record.get('source_mtime'),
                            sha256=record.get('source_sha256_after'),
                            folder=record.get('available_in') if record.get('status') == 'skipped-unchanged' else cand.name)
                used += 1
            except OSError:
                continue
        if used:
            self.update(detail='Incremental mode: loaded ' + str(len(self.previous)) + ' previously verified files from ' + str(used) + ' earlier backup(s).')

    def unchanged(self, remote, size, mtime):
        """Return the earlier record when this file is provably unchanged, else None."""
        prev = self.previous.get(remote)
        if not prev or prev.get('bytes') is None or size is None or prev['bytes'] != size:
            return None
        if prev.get('mtime') and mtime and prev['mtime'] == mtime:
            return prev
        # Same size but no trustworthy timestamps: prove identity with a hash.
        if prev.get('sha256'):
            try:
                if self.remote_hash(remote) == prev['sha256']:
                    return prev
            except BackupError:
                return None
        return None

    def start(self, destination, options=None):
        options = selection.validate(options)
        with self.lock:
            if self.state['running']:
                return False
            self.stop.clear()
            self.resume_gate.set()
            self.resume_check = False
            self.options = options
            self.progress = CopyProgress()
            self.previous = {}
            self.state = dict(phase='Connecting', detail='Checking phone access...', running=True, mode='backup',
                              total=0, done=0, verified=0, failed=0, skipped=0, vcf=0, folder='',
                              warnings=[], recent=[], categories={}, scanned=0, excluded=0,
                              paused=False, pause_requested=False, selection=json.loads(json.dumps(options)),
                              adb_setup=self.state.get('adb_setup'))
        threading.Thread(target=self.backup, args=(destination,), daemon=True).start()
        return True

    def backup(self, destination):
        folder = None
        records = None
        summary = dict(version=VERSION, started=dt.datetime.now().astimezone().isoformat(),
                       scope='Selected readable shared-storage files and selected permitted providers only. NOT a full phone backup.', gaps=GAPS, selection=self.options)
        try:
            info = self.connect()
            summary['device'] = info
            destination = Path(destination).expanduser().resolve()
            destination.mkdir(parents=True, exist_ok=True)
            # Separate new folder every time. Existing backups are never overwritten.
            folder = destination / ('megahy-backup-' + dt.datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(3))
            folder.mkdir()
            if self.options['incremental'] and self.options['storage'] != 'none':
                self.update(detail='Loading earlier backups for incremental mode...')
                self.load_previous(destination, folder.name)
            self.update(folder=str(folder), detail=info['model'] + ' / Android ' + info['android'])
            (folder / 'READ-FIRST.txt').write_text('\n\n'.join(GAPS), encoding='utf-8')
            # Local provider archives never write anything onto the phone.
            from autoexports import export_all
            summary['automatic_categories'] = export_all(self, folder, selected=self.options['providers'])
            inventory = []
            scan_roots = []
            scanned = 0
            scan_errors = 0
            excluded = dict(hidden=0, cache=0, type=0)
            if self.options['storage'] != 'none':
                self.update(phase='Scanning selected storage')
                code, out, err = self.shell('sha256sum /dev/null')
                if code or not re.match(rb'[0-9a-fA-F]{64}', out):
                    raise BackupError('This phone does not provide the SHA-256 tool required by this preview. No unverified backup will be presented as verified.')
                if self.options['storage'] == 'folder':
                    scan_roots = [selection.folder_scope(self.options['folder'])]
                    code, _, _ = self.shell('test -d ' + shlex.quote(scan_roots[0][2]))
                    if code:
                        raise BackupError('Selected folder is missing or not readable: ' + scan_roots[0][2])
                else:
                    scan_roots = [(label, root, root) for label, root in self.roots()]
                for label, root, scan_root in scan_roots:
                    self.update(detail='Scanning ' + scan_root + '...')
                    try:
                        for remote in self.inventory(scan_root):
                            scanned += 1
                            reason = selection.exclusion(remote, root, self.options)
                            if reason:
                                excluded[reason] += 1
                            else:
                                inventory.append((label, root, remote))
                    except Cancelled:
                        raise
                    except BackupError as e:
                        scan_errors += 1
                        self.warn(str(e))
                self.update(total=len(inventory), scanned=scanned, excluded=sum(excluded.values()))
                summary['excluded_files'] = dict(excluded)
                if scan_roots and scan_errors == len(scan_roots):
                    raise BackupError('No selected storage root could be scanned safely. Provider archives, if any, do not make this storage backup complete.')
                if not inventory:
                    if not any(r.get('records', 0) or r.get('exported_vcards', 0) or r.get('attachments_saved', 0) for r in self.snapshot()['categories'].values()):
                        raise BackupError('No readable files matched your selection and no selected provider records were exported. Review the selection, category report and scan warnings.')
                    self.warn('No readable storage files matched the selection. Only selected provider attempts may have exported data.')
                if self.options['storage'] in ('photos', 'videos', 'media'):
                    self.warn('Media selection uses filename extensions only. Missing/unusual extensions can be omitted. This is not every photo or video on the phone.')
                if not self.options['include_hidden'] or not self.options['include_cache']:
                    self.warn('Hidden/cache exclusions were selected. These can omit wanted files, including media. Nothing was deleted from the phone.')
            if self.options['storage'] == 'none' and not any(r.get('records', 0) or r.get('exported_vcards', 0) or r.get('attachments_saved', 0) for r in self.snapshot()['categories'].values()):
                raise BackupError('No selected provider records were exported. Review whether the category is empty, partial or unavailable. Nothing from shared storage was requested.')
            (folder / 'inventory.json').write_text(json.dumps(inventory, ensure_ascii=True, indent=2), encoding='utf-8')
            summary.update(scanned_files=scanned, selected_files=len(inventory), excluded_files=excluded)
            sizes = {}
            mtimes = {}
            if inventory:
                self.update(phase='Measuring selected file sizes', detail='Preparing byte counts for a rough ETA...')
                sizes, mtimes = self.measure_meta(inventory)
                (folder / 'source-sizes-reference.json').write_text(json.dumps(sizes, ensure_ascii=True, indent=2), encoding='utf-8')
                self.progress.begin(sizes)
                # Free-space precheck against measured selected bytes.
                known = sum(n for n in sizes.values() if n is not None)
                if self.previous:
                    pending = sum(sizes.get(r, 0) or 0 for _, _, r in inventory
                                  if not (sizes.get(r) is not None and self.previous.get(r)
                                          and self.previous[r].get('bytes') == sizes.get(r)
                                          and self.previous[r].get('mtime') and mtimes.get(r)
                                          and self.previous[r]['mtime'] == mtimes.get(r)))
                else:
                    pending = known
                free = shutil.disk_usage(str(destination)).free
                if pending and free < pending + 64 * 1024 * 1024:
                    raise BackupError('Not enough free disk space at the destination: about ' + str(pending // (1024 * 1024)) + ' MiB are needed for this selection but only ' + str(free // (1024 * 1024)) + ' MiB are free. Free space or choose another folder.')
            records = open(folder / 'manifest.jsonl', 'w', encoding='utf-8')
            mapper = NameMapper()
            self.update(phase='Copying and verifying')
            for index, (label, root, remote) in enumerate(inventory, 1):
                self.update(detail=remote, done=index-1)
                record = dict(source=remote, storage=label, status='failed')
                partial = None
                try:
                    if self.stop.is_set():
                        raise Cancelled('Stopped by user')
                    if mtimes.get(remote) is not None:
                        record['source_mtime'] = mtimes[remote]
                    # Incremental: skip files already verified unchanged in an earlier backup.
                    prev = self.unchanged(remote, sizes.get(remote), mtimes.get(remote)) if self.previous else None
                    if prev:
                        record.update(status='skipped-unchanged', bytes=sizes.get(remote),
                                      source_sha256_after=prev.get('sha256'),
                                      available_in=prev.get('folder'))
                        with self.lock:
                            self.state['skipped'] += 1
                        records.write(json.dumps(record, ensure_ascii=True) + '\n')
                        records.flush()
                        self.progress.record(remote, record.get('bytes', 0))
                        self.update(done=index)
                        continue
                    rel = mapper.map(label + '/' + remote[len(root):])
                    target = folder / 'files' / rel
                    record['local'] = str(Path('files') / rel)
                    os.makedirs(local_path(target.parent), exist_ok=True)
                    partial = target.with_name(target.name + '.partial')
                    before = self.remote_hash(remote)
                    code, out, err = self.run(['pull', '-a', remote, local_path(partial)], timeout=7200)
                    if code:
                        error_text = err.decode('utf-8', 'replace')
                        # adb writes the PC file itself, so ENOSPC can arrive as
                        # stderr rather than a Python OSError in this process.
                        if re.search(r'no space left on device|disk (?:is )?full|not enough space|insufficient disk space|\bENOSPC\b', error_text, re.I):
                            raise OSError(28, 'PC disk is full during ADB pull')
                        raise BackupError('Copy failed: ' + error_text[:600])
                    pc_hash = digest(partial)
                    after = self.remote_hash(remote)
                    record.update(source_sha256_before=before, source_sha256_after=after, local_sha256=pc_hash)
                    if before != after or before != pc_hash:
                        raise BackupError('Hash mismatch or source changed during copy. File is not verified.')
                    os.replace(local_path(partial), local_path(target))
                    # Preserve the phone's modification date on the PC copy.
                    if mtimes.get(remote):
                        try:
                            os.utime(local_path(target), (mtimes[remote], mtimes[remote]))
                            record['mtime_preserved'] = True
                        except OSError:
                            record['mtime_preserved'] = False
                    record.update(status='verified', bytes=os.path.getsize(local_path(target)))
                    with self.lock:
                        self.state['verified'] += 1
                    if remote.lower().endswith('.vcf'):
                        with open(local_path(target), 'rb') as v:
                            if b'BEGIN:VCARD' in v.read(65536).upper():
                                with self.lock:
                                    self.state['vcf'] += 1
                except Cancelled:
                    record['error'] = 'Run stopped before this file was verified'
                    with self.lock:
                        self.state['failed'] += 1
                    raise
                except Exception as e:
                    record['error'] = str(e)
                    with self.lock:
                        self.state['failed'] += 1
                    if isinstance(e, DeviceDisconnected):
                        raise
                    if isinstance(e, OSError) and getattr(e, 'errno', None) == 28:
                        raise BackupError('PC disk is full. This backup is incomplete.')
                    connected, _, _ = self.run(['get-state'], timeout=15)
                    if connected:
                        raise BackupError('Phone disconnected. This backup is incomplete. Reconnect and start a new run.')
                finally:
                    if record.get('status') != 'skipped-unchanged':
                        records.write(json.dumps(record, ensure_ascii=True) + '\n')
                        records.flush()
                        self.progress.record(remote, record.get('bytes', 0))
                        self.update(done=index)
            # A second inventory spots newly added or removed files. This is still not a snapshot.
            self.update(phase='Checking for storage changes')
            for label, root, scan_root in scan_roots:
                try:
                    old = {p for l, r, p in inventory if r == root}
                    new = {p for p in self.inventory(scan_root) if selection.exclusion(p, root, self.options) is None}
                    if old != new:
                        self.warn('File list changed during backup in ' + label + ': ' + str(len(new-old)) + ' added, ' + str(len(old-new)) + ' removed. Run another backup after stopping phone activity.')
                except Cancelled:
                    raise
                except BackupError as e:
                    self.warn('End-of-run rescan failed: ' + str(e))
            if 'contacts' in self.options['providers'] and not self.snapshot()['vcf'] and not self.snapshot()['categories'].get('contacts', {}).get('exported_vcards', 0):
                self.warn('No contacts vCards were exported or found in verified storage copies. Contacts have NOT been confirmed backed up.')
            self.update(phase='Finished with gaps', detail='Review the report. This is not proof that the phone is safe to reset.')
        except Cancelled:
            self.update(phase='Stopped, incomplete', detail='The run stopped. Already verified files remain; do not treat this as a complete backup.')
        except Exception as e:
            self.update(phase='Error, incomplete', detail=str(e))
        finally:
            final_categories = self.snapshot()['categories']
            for name, result in final_categories.items():
                if result.get('status') in ('pending', 'reading'):
                    final_categories[name] = {'status':'incomplete', 'note':'Selected, but this run ended before the archive completed. Do not treat partial files as a completed export.'}
            self.update(categories=final_categories)
            if records:
                try:
                    records.close()
                except Exception as e:
                    self.update(phase='Error, incomplete', detail='Could not finish the per-file manifest: ' + str(e))
            if folder:
                summary.update(self.snapshot())
                summary.update(running=False, paused=False, pause_requested=False)
                summary['finished'] = dt.datetime.now().astimezone().isoformat()
                try:
                    category_path = folder / 'automatic-exports' / 'category-report.json'
                    if category_path.parent.is_dir():
                        category_path.write_text(json.dumps(summary['categories'], ensure_ascii=True, indent=2), encoding='utf-8')
                    (folder / 'report.json').write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding='utf-8')
                    text = '\n'.join([summary['phase'], summary['detail'], '',
                          'SELECTION:', json.dumps(self.options, ensure_ascii=True, indent=2), '',
                          'Scanned readable files: ' + str(summary['scanned']),
                          'Excluded by selection: ' + str(summary['excluded']),
                          'Selected files: ' + str(summary['total']), 'Attempted: ' + str(summary['done']),
                          'Verified: ' + str(summary['verified']),
                          'Skipped unchanged (kept in an earlier backup folder): ' + str(summary.get('skipped', 0)),
                          'Failed: ' + str(summary['failed']),
                          'Existing contact-export files found (not completeness-checked): ' + str(summary['vcf']),
                          'AUTOMATIC PROVIDER CATEGORIES (not restore-tested):', json.dumps(summary['categories'], ensure_ascii=True, indent=2), '',
                          'WARNINGS:', *summary['warnings'], '', 'ALWAYS EXCLUDED / NOT GUARANTEED:', *GAPS,
                          '', 'See manifest.jsonl for per-file paths, hashes, dates and failures. See inventory.json for discovered files.'])
                    (folder / 'REPORT.txt').write_text(text, encoding='utf-8')
                except Exception as e:
                    self.update(phase='Error, incomplete', detail='Could not write the final report: ' + str(e))
            self.resume_gate.set()
            self.update(running=False, paused=False, pause_requested=False)

    # ----- Restore (copies verified files back to the phone; writes to the phone) -----

    def list_backups(self, destination):
        """Previous backup folders in a destination, newest first."""
        destination = Path(destination).expanduser().resolve()
        result = []
        if not destination.is_dir():
            return result
        for cand in sorted((p for p in destination.glob('megahy-backup-*') if p.is_dir()), key=lambda p: p.name, reverse=True):
            entry = {'name': cand.name}
            report = cand / 'report.json'
            if report.is_file():
                try:
                    data = json.loads(report.read_text(encoding='utf-8'))
                    entry.update(verified=data.get('verified'), failed=data.get('failed'),
                                 started=data.get('started'), phase=data.get('phase'))
                except Exception:
                    pass
            entry['files_present'] = (cand / 'files').is_dir()
            result.append(entry)
        return result[:30]

    def start_restore(self, destination, backup_name, target):
        with self.lock:
            if self.state['running']:
                return False
            destination = Path(destination).expanduser().resolve()
            if not re.fullmatch(r'megahy-backup-[0-9]{8}-[0-9]{6}-[0-9a-f]{6}', backup_name or ''):
                raise ValueError('Choose a backup folder made by this app')
            folder = destination / backup_name
            if not folder.is_dir() or folder.parent != destination:
                raise ValueError('That backup folder was not found in the destination')
            _, _, target = selection.folder_scope(target)
            self.stop.clear()
            self.resume_gate.set()
            self.resume_check = False
            self.progress = CopyProgress()
            self.state = dict(phase='Connecting', detail='Checking phone access...', running=True, mode='restore',
                              total=0, done=0, verified=0, failed=0, skipped=0, vcf=0, folder=str(folder),
                              warnings=[], recent=[], categories={}, scanned=0, excluded=0,
                              paused=False, pause_requested=False, selection=selection.defaults(),
                              adb_setup=self.state.get('adb_setup'))
        threading.Thread(target=self.restore, args=(folder, target), daemon=True).start()
        return True

    def restore(self, folder, target):
        records = None
        try:
            info = self.connect()
            self.update(detail=info['model'] + ' / Android ' + info['android'])
            manifest = folder / 'manifest.jsonl'
            if not manifest.is_file():
                raise BackupError('This backup folder has no manifest.jsonl to restore from.')
            wanted = []
            with open(manifest, encoding='utf-8') as f:
                for line in f:
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue
                    if record.get('status') == 'verified' and record.get('local') and record.get('local_sha256'):
                        local_file = folder / record['local']
                        if local_file.is_file():
                            wanted.append((record, local_file))
            if not wanted:
                raise BackupError('No verified files from this backup are still present on the PC. Nothing to restore.')
            stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
            target_root = target.rstrip('/') + '/megahy-backup-restore-' + stamp
            code, _, err = self.shell('mkdir -p ' + shlex.quote(target_root))
            if code:
                raise BackupError('Could not create the restore folder on the phone: ' + err.decode('utf-8', 'replace')[:400])
            restore_dir = folder / 'restores' / ('restore-' + stamp)
            restore_dir.mkdir(parents=True, exist_ok=True)
            records = open(restore_dir / 'restore-manifest.jsonl', 'w', encoding='utf-8')
            self.update(phase='Restoring files to the phone', total=len(wanted))
            self.warn('Restore copies files into ' + target_root + ' on the phone. It does not put contacts, messages or app data back into their apps.')
            for index, (record, local_file) in enumerate(wanted, 1):
                self.update(detail=str(record['local']), done=index-1)
                out_record = dict(source=record.get('source'), local=record.get('local'), status='failed')
                try:
                    if self.stop.is_set():
                        raise Cancelled('Stopped by user')
                    # Rebuild the phone-relative path from the original source path.
                    dest = target_root + '/' + '/'.join(PurePosixPath(record['local']).parts[2:])
                    parent = str(PurePosixPath(dest).parent)
                    code, _, err = self.shell('mkdir -p ' + shlex.quote(parent))
                    if code:
                        raise BackupError('Could not create folder on the phone: ' + err.decode('utf-8', 'replace')[:300])
                    code, out, err = self.run(['push', local_path(local_file), dest], timeout=7200)
                    if code:
                        raise BackupError('Push failed: ' + err.decode('utf-8', 'replace')[:600])
                    phone_hash = self.remote_hash(dest)
                    out_record['phone_sha256'] = phone_hash
                    if phone_hash == record['local_sha256']:
                        out_record['status'] = 'restored-verified'
                        with self.lock:
                            self.state['verified'] += 1
                    else:
                        out_record['status'] = 'restored-unverified'
                        out_record['error'] = 'Hash on the phone does not match the backed-up file.'
                        with self.lock:
                            self.state['failed'] += 1
                except Cancelled:
                    out_record['error'] = 'Run stopped before this file was restored'
                    with self.lock:
                        self.state['failed'] += 1
                    raise
                except Exception as e:
                    out_record['error'] = str(e)
                    with self.lock:
                        self.state['failed'] += 1
                    if isinstance(e, DeviceDisconnected):
                        raise
                finally:
                    records.write(json.dumps(out_record, ensure_ascii=True) + '\n')
                    records.flush()
                    self.progress.record(record.get('source'), record.get('bytes', 0))
                    self.update(done=index)
            self.update(phase='Restore finished', detail='Files were copied to ' + target_root + '. Check them on the phone before relying on them.')
        except Cancelled:
            self.update(phase='Stopped, incomplete', detail='The restore stopped. Files already pushed remain on the phone.')
        except Exception as e:
            self.update(phase='Error, incomplete', detail=str(e))
        finally:
            if records:
                try:
                    records.close()
                except Exception:
                    pass
            self.resume_gate.set()
            self.update(running=False, paused=False, pause_requested=False)


def serve(engine, port=0, open_browser=True):
    token = secrets.token_urlsafe(32)

    def persisted():
        return app_settings.load(BASE)

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, code, data, kind='application/json'):
            body = data if isinstance(data, bytes) else json.dumps(data).encode()
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            host = '127.0.0.1:' + str(self.server.server_port)
            return self.headers.get('Host') == host and secrets.compare_digest(self.headers.get('X-megahy-backup-Token', ''), token) and self.headers.get('Origin', 'http://' + host) == 'http://' + host

        def do_GET(self):
            if self.path == '/':
                self.reply(200, (BASE / 'ui.html').read_bytes(), 'text/html; charset=utf-8')
            elif self.path == '/api/state' and self.authorized():
                saved = persisted()
                last_auto = None
                try:
                    auto_file = BASE / 'last-auto-run.json'
                    if auto_file.is_file():
                        last_auto = json.loads(auto_file.read_text(encoding='utf-8'))
                except Exception:
                    last_auto = None
                try:
                    scheduled = scheduler.status()
                except Exception:
                    scheduled = None
                self.reply(200, dict(engine.snapshot(),
                                     default_destination=saved['destination'] or str(Path.home() / 'megahy-backup'),
                                     saved_selection=saved['selection'],
                                     theme=saved['theme'], language=saved['language'],
                                     profiles=sorted(saved['profiles'].keys()),
                                     adb_present=bool(adbtools.find_adb(BASE) or engine.adb),
                                     os_name=os.name,
                                     scheduled=scheduled, schedule=saved.get('schedule'),
                                     last_auto=last_auto, version=VERSION))
            else:
                self.reply(403, {'error': 'Not allowed'})

        def do_POST(self):
            if not self.authorized():
                return self.reply(403, {'error': 'Not allowed'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length < 0 or length > 65536:
                    raise ValueError('Invalid request size')
                data = json.loads(self.rfile.read(length) or b'{}')
                if self.path == '/api/start':
                    if data.get('acknowledged') is not True:
                        raise ValueError('Read and accept the scope notice first')
                    destination = data.get('destination')
                    if not isinstance(destination, str) or not destination.strip():
                        raise ValueError('Choose a backup folder')
                    options = selection.validate(data.get('selection'))
                    if not engine.start(destination.strip(), options):
                        return self.reply(409, {'error': 'A backup is already running'})
                    saved = persisted()
                    saved['destination'] = destination.strip()
                    saved['selection'] = options
                    app_settings.save(BASE, saved)
                elif self.path == '/api/pause':
                    engine.request_pause()
                elif self.path == '/api/resume':
                    engine.resume()
                elif self.path == '/api/stop':
                    engine.request_stop()
                elif self.path == '/api/browse-folder':
                    if engine.snapshot()['running']:
                        return self.reply(409, {'error': 'Finish or stop the current run before changing the folder'})
                    path = pick_folder()
                    self.reply(200, {'ok': True, 'path': path, 'cancelled': path == ''})
                    return
                elif self.path == '/api/open':
                    folder = engine.snapshot()['folder']
                    if os.name == 'nt' and folder and Path(folder).is_dir():
                        os.startfile(folder)
                    else:
                        raise ValueError('Open this folder manually: ' + folder)
                elif self.path == '/api/preferences':
                    saved = persisted()
                    if data.get('theme') in ('light', 'dark'):
                        saved['theme'] = data['theme']
                    if data.get('language') in ('en', 'ar'):
                        saved['language'] = data['language']
                    app_settings.save(BASE, saved)
                elif self.path == '/api/profiles':
                    saved = persisted()
                    action = data.get('action')
                    name = data.get('name')
                    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 60:
                        raise ValueError('Profile name must be 1-60 characters')
                    name = name.strip()
                    if action == 'save':
                        destination = data.get('destination')
                        if not isinstance(destination, str) or not destination.strip():
                            raise ValueError('Choose a backup folder before saving a profile')
                        saved['profiles'][name] = dict(destination=destination.strip(),
                                                       selection=selection.validate(data.get('selection')))
                        app_settings.save(BASE, saved)
                    elif action == 'delete':
                        saved['profiles'].pop(name, None)
                        app_settings.save(BASE, saved)
                    else:
                        raise ValueError('Unknown profile action')
                    self.reply(200, {'ok': True, 'profiles': sorted(saved['profiles'].keys())})
                    return
                elif self.path == '/api/profile-load':
                    saved = persisted()
                    profile = saved['profiles'].get(data.get('name'))
                    if not profile:
                        raise ValueError('Profile not found')
                    self.reply(200, {'ok': True, 'destination': profile['destination'], 'selection': profile['selection']})
                    return
                elif self.path == '/api/setup-adb':
                    engine.setup_adb_async()
                elif self.path == '/api/wifi-pair':
                    engine.pair_wifi(data.get('host'), data.get('port'), data.get('code'))
                elif self.path == '/api/wifi-connect':
                    serial = engine.connect_wifi(data.get('host'), data.get('port'))
                    self.reply(200, {'ok': True, 'serial': serial})
                    return
                elif self.path == '/api/restore-list':
                    destination = data.get('destination')
                    if not isinstance(destination, str) or not destination.strip():
                        raise ValueError('Choose the destination folder that holds your backups')
                    self.reply(200, {'ok': True, 'backups': engine.list_backups(destination.strip())})
                    return
                elif self.path == '/api/restore':
                    destination = data.get('destination')
                    if not isinstance(destination, str) or not destination.strip():
                        raise ValueError('Choose the destination folder that holds your backups')
                    target = data.get('target') or '/sdcard/'
                    if not engine.start_restore(destination.strip(), data.get('backup'), target):
                        return self.reply(409, {'error': 'Another run is already active'})
                elif self.path == '/api/schedule':
                    info = scheduler.install(BASE, data.get('frequency'), data.get('time'))
                    saved = persisted()
                    saved['schedule'] = {'frequency': data.get('frequency'), 'time': data.get('time')}
                    app_settings.save(BASE, saved)
                    self.reply(200, {'ok': True, 'scheduled': True, 'task': info})
                    return
                elif self.path == '/api/schedule-delete':
                    scheduler.remove()
                    saved = persisted()
                    saved['schedule'] = {}
                    app_settings.save(BASE, saved)
                    self.reply(200, {'ok': True, 'scheduled': False})
                    return
                else:
                    return self.reply(404, {'error': 'Unknown action'})
                self.reply(200, {'ok': True})
            except Exception as e:
                self.reply(400, {'error': str(e)})

    server = http.server.ThreadingHTTPServer(('127.0.0.1', port), Handler)
    url = 'http://127.0.0.1:' + str(server.server_port) + '/#' + token
    print('megahy-backup is running locally. Keep this window open.\n' + url, flush=True)
    if open_browser:
        webbrowser.open(url)
    return server, url


def run_auto():
    """Headless scheduled backup using the last saved settings. Exit 0 on the
    normal completed phase, 1 otherwise."""
    saved = app_settings.load(BASE)
    destination = saved['destination'] or str(Path.home() / 'megahy-backup')
    options = selection.validate(saved['selection'])
    engine = Engine()
    engine.start(destination, options)
    while True:
        snap = engine.snapshot()
        if not snap['running']:
            break
        print(snap['phase'] + ': ' + snap.get('detail', ''), flush=True)
        time.sleep(2)
    snap = engine.snapshot()
    record = {'finished': dt.datetime.now().astimezone().isoformat(), 'phase': snap['phase'],
              'verified': snap['verified'], 'failed': snap['failed'], 'skipped': snap.get('skipped', 0),
              'folder': snap['folder']}
    try:
        (BASE / 'last-auto-run.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    except OSError:
        pass
    print('Automatic backup ended: ' + snap['phase'], flush=True)
    return 0 if snap['phase'] == 'Finished with gaps' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--auto', action='store_true', help='Run one unattended backup with the saved settings (used by the scheduler).')
    args = parser.parse_args()
    if args.auto:
        sys.exit(run_auto())
    server, _ = serve(Engine(), args.port, not args.no_browser)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
