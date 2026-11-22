# Copyright (c) 2026 CableVault contributors and Marwan Megahy
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License version 3 or (at your option) any later
# version. See LICENSE.txt. Code inherited from the CableVault preview remains under
# the MIT license; see NOTICE.txt.
"""megahy-backup 0.3.1-rc2 preview. Standard-library-only, read-only Android USB backup."""
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
from eta import CopyProgress

# Keep cancellation types identical when launched as a script.
sys.modules.setdefault('megahy_backup', sys.modules[__name__])
BASE = Path(__file__).resolve().parent
GAPS = [
    'This is a file backup, not a full phone clone or a reset-safety certificate.',
    'Private app data, installed apps, logins, passwords, authenticator secrets, WhatsApp/Signal chats, system settings and eSIMs are not extracted. Contacts, SMS, MMS and call-log provider exports are attempted only when the Android shell is already allowed to read them.',
    'Automatic provider exports can be denied by Android. Contacts use provider vCards when available. SMS/call logs use JSON and CSV; MMS uses JSON and binary parts. These are archival exports, not tested Android-restorable backups. Provider visibility does not prove completeness.',
    'Cloud-only photos, locked/secure folders, work profiles, other users and unmounted or unusually named storage volumes may be missing.',
    'Android may deny access or hide files from the shell even inside shared storage. Unreadable files may be absent. Empty directories are not copied.',
    'Only the chosen categories and folders are attempted. Media filters use filename extensions, not content. Hidden/cache exclusions may omit wanted files; they never delete or free space on the phone.',
    'A live phone is not a snapshot. Stop using it during backup, then check important files and each app backup before considering a reset.',
    'Backups are not encrypted by this app. Protect the backup disk. This app has no automatic restore; files can be copied back, but app-specific restoration needs its own tools.'
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


class Engine:
    def __init__(self, adb=None):
        self.adb = adb
        self.serial = None
        self.options = selection.defaults()
        self.progress = CopyProgress()
        self.stop = threading.Event()
        self.resume_gate = threading.Event()
        self.resume_gate.set()
        self.resume_check = False
        self.lock = threading.Lock()
        self.state = dict(phase='Ready', detail='Connect one unlocked Android phone by USB.', running=False,
                          total=0, done=0, verified=0, failed=0, vcf=0, folder='', warnings=[], recent=[], categories={}, miui_backup_files=0, scanned=0, excluded=0, paused=False, pause_requested=False, selection=selection.defaults())

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
                    raise DeviceDisconnected('Phone unavailable after Pause. This backup is incomplete. Reconnect and start a new run; no partial file is verified.')
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
                    raise BackupError('ADB timed out. Check the cable and phone; this run is incomplete.')
                time.sleep(.08)
            out.seek(0)
            err.seek(0)
            return p.returncode, out.read(), err.read()

    def shell(self, command, timeout=120):
        return self.run(['shell', command], timeout=timeout)

    def connect(self):
        choices = [BASE / 'platform-tools' / 'adb.exe', BASE / 'platform-tools' / 'adb',
                   BASE / 'adb.exe']
        self.adb = self.adb or next((str(p) for p in choices if p.is_file()), None) or shutil.which('adb')
        if not self.adb:
            raise BackupError('ADB not found. Download Google Platform-Tools and place its platform-tools folder next to START-megahy-backup.cmd. See README.txt.')
        code, out, err = self.run(['-d', 'get-serialno'], device=False)
        serial = out.decode('utf-8', 'replace').strip()
        if code or not serial or serial == 'unknown':
            raise BackupError('Connect exactly ONE USB phone, unlock it and accept Allow USB debugging. If it is still missing, check the cable and manufacturer USB driver. ADB: ' + err.decode('utf-8', 'replace')[:400])
        self.serial = serial
        code, out, _ = self.shell('getprop ro.product.model')
        model = out.decode('utf-8', 'replace').strip() if not code else 'Android phone'
        _, version, _ = self.shell('getprop ro.build.version.release')
        return dict(model=model, android=version.decode('utf-8', 'replace').strip(), serial=serial)

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

    def measure_sizes(self, inventory):
        # Optional metadata only. Batches avoid an extra PC subprocess per file.
        sizes = {remote:None for _, _, remote in inventory}
        batches=[];batch=[];length=0
        for _, _, remote in inventory:
            quoted=shlex.quote(remote)
            if batch and (len(batch)>=64 or length+len(quoted)>6000):
                batches.append(batch);batch=[];length=0
            batch.append(remote);length+=len(quoted)+1
        if batch:batches.append(batch)
        failures=0
        for index,batch in enumerate(batches,1):
            self.update(detail='Measuring selected file sizes: batch '+str(index)+' of '+str(len(batches)))
            try:
                code,out,err=self.shell('stat -c %s -- '+' '.join(shlex.quote(p) for p in batch),timeout=900)
                lines=out.decode('ascii').splitlines()
                if code or err.strip() or len(lines)!=len(batch) or any(not re.fullmatch(r'[0-9]+',line) for line in lines):
                    failures+=1
                    if code==127 or failures>=5:break
                    continue
                for remote,line in zip(batch,lines):sizes[remote]=int(line)
            except (Cancelled,DeviceDisconnected):
                raise
            except Exception:
                break
        unknown=sum(n is None for n in sizes.values())
        if unknown:self.warn('Could not measure '+str(unknown)+' selected file sizes. Backup can continue; the rough ETA has incomplete byte information.')
        return sizes

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
            self.state = dict(phase='Connecting', detail='Checking USB access...', running=True,
                              total=0, done=0, verified=0, failed=0, vcf=0, folder='', warnings=[], recent=[], categories={}, miui_backup_files=0, scanned=0, excluded=0, paused=False, pause_requested=False, selection=json.loads(json.dumps(options)))
        threading.Thread(target=self.backup, args=(destination,), daemon=True).start()
        return True

    def backup(self, destination):
        folder = None
        records = None
        summary = dict(version='0.3.1-rc2', started=dt.datetime.now().astimezone().isoformat(),
                       scope='Selected readable shared-storage files and selected permitted providers only. NOT a full phone backup.', gaps=GAPS, selection=self.options)
        try:
            info = self.connect()
            summary['device'] = info
            destination = Path(destination).expanduser().resolve()
            destination.mkdir(parents=True, exist_ok=True)
            # Separate new folder every time. Existing backups are never overwritten.
            folder = destination / ('megahy-backup-' + dt.datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(3))
            folder.mkdir()
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
            self.update(miui_backup_files=sum(1 for _,root,path in inventory if path[len(root):].lower().startswith('miui/backup/allbackup/')))
            sizes = {}
            if inventory:
                self.update(phase='Measuring selected file sizes', detail='Preparing byte counts for a rough ETA...')
                sizes = self.measure_sizes(inventory)
                (folder / 'source-sizes-reference.json').write_text(json.dumps(sizes, ensure_ascii=True, indent=2), encoding='utf-8')
                self.progress.begin(sizes)
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
                    rel = mapper.map(label + '/' + remote[len(root):])
                    target = folder / 'files' / rel
                    record['local'] = str(Path('files') / rel)
                    os.makedirs(local_path(target.parent), exist_ok=True)
                    partial = target.with_name(target.name + '.partial')
                    before = self.remote_hash(remote)
                    code, out, err = self.run(['pull', remote, local_path(partial)], timeout=7200)
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
                          'Verified: ' + str(summary['verified']), 'Failed: ' + str(summary['failed']),
                          'Existing contact-export files found (not completeness-checked): ' + str(summary['vcf']),
                          'Existing MIUI backup files discovered: ' + str(summary['miui_backup_files']),
                          'AUTOMATIC PROVIDER CATEGORIES (not restore-tested):', json.dumps(summary['categories'], ensure_ascii=True, indent=2), '',
                          'WARNINGS:', *summary['warnings'], '', 'ALWAYS EXCLUDED / NOT GUARANTEED:', *GAPS,
                          '', 'See manifest.jsonl for per-file paths, hashes and failures. See inventory.json for discovered files.'])
                    (folder / 'REPORT.txt').write_text(text, encoding='utf-8')
                except Exception as e:
                    self.update(phase='Error, incomplete', detail='Could not write the final report: ' + str(e))
            self.resume_gate.set()
            self.update(running=False, paused=False, pause_requested=False)


def serve(engine, port=0, open_browser=True):
    token = secrets.token_urlsafe(32)
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
                self.reply(200, dict(engine.snapshot(), default_destination=str(Path.home() / 'megahy-backup')))
            else:
                self.reply(403, {'error': 'Not allowed'})

        def do_POST(self):
            if not self.authorized():
                return self.reply(403, {'error': 'Not allowed'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length < 0 or length > 8192:
                    raise ValueError('Invalid request size')
                data = json.loads(self.rfile.read(length) or b'{}')
                if self.path == '/api/start':
                    if data.get('acknowledged') is not True:
                        raise ValueError('Read and accept the scope notice first')
                    destination = data.get('destination')
                    if not isinstance(destination, str) or not destination.strip():
                        raise ValueError('Choose a backup folder')
                    options = selection.validate(data.get('selection'))
                    if not engine.start(destination, options):
                        return self.reply(409, {'error': 'A backup is already running'})
                elif self.path == '/api/pause':
                    engine.request_pause()
                elif self.path == '/api/resume':
                    engine.resume()
                elif self.path == '/api/stop':
                    engine.request_stop()
                elif self.path == '/api/open':
                    folder = engine.snapshot()['folder']
                    if os.name == 'nt' and folder and Path(folder).is_dir():
                        os.startfile(folder)
                    else:
                        raise ValueError('Open this folder manually: ' + folder)
                else:
                    return self.reply(404, {'error': 'Unknown action'})
                self.reply(200, {'ok': True})
            except Exception as e:
                self.reply(400, {'error': str(e)})

    server = http.server.ThreadingHTTPServer(('127.0.0.1', port), Handler)
    url = 'http://127.0.0.1:' + str(server.server_port) + '/#' + token
    print('megahy-backup preview is running locally. Keep this window open.\n' + url, flush=True)
    if open_browser:
        webbrowser.open(url)
    return server, url


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    server, _ = serve(Engine(), args.port, not args.no_browser)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
