# Copyright (c) 2026 Marwan Megahy
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License version 3 or (at your option) any later
# version. See LICENSE.txt.
"""Locate or download Google's official Platform-Tools (adb) for this PC."""
import os
from pathlib import Path
import shutil
import stat
import sys
import urllib.request
import zipfile

# Official Google download endpoints. MEGAHY_ADB_URL is a test hook only.
URLS = {
    'nt': 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip',
    'darwin': 'https://dl.google.com/android/repository/platform-tools-latest-darwin.zip',
    'linux': 'https://dl.google.com/android/repository/platform-tools-latest-linux.zip',
}
MIN_ZIP_BYTES = 4 * 1024 * 1024  # the real archive is far larger; a smaller file is an error page


class AdbSetupError(Exception):
    pass


def _platform_key():
    if os.name == 'nt':
        return 'nt'
    if sys.platform == 'darwin':
        return 'darwin'
    return 'linux'


def find_adb(base):
    """Return the adb executable path, or None."""
    base = Path(base)
    names = ['adb.exe', 'adb'] if os.name == 'nt' else ['adb', 'adb.exe']
    for name in names:
        candidate = base / 'platform-tools' / name
        if candidate.is_file():
            return str(candidate)
    candidate = base / names[0]
    if candidate.is_file():
        return str(candidate)
    return shutil.which('adb')


def download_url():
    return os.environ.get('MEGAHY_ADB_URL') or URLS[_platform_key()]


def download_and_install(base, progress=None):
    """Download Google's Platform-Tools ZIP and extract it next to the app.

    progress(percent:int|None, stage:str) reports download/extract stages.
    Returns the adb path. Raises AdbSetupError with a readable message.
    """
    base = Path(base)
    url = download_url()
    target = base / 'platform-tools-download.zip'

    def report(percent, stage):
        if progress:
            progress(percent, stage)

    try:
        report(0, 'downloading')
        request = urllib.request.Request(url, headers={'User-Agent': 'megahy-backup-setup'})
        with urllib.request.urlopen(request, timeout=120) as response:
            total = int(response.headers.get('Content-Length') or 0)
            received = 0
            with open(target, 'wb') as out:
                while True:
                    block = response.read(1024 * 256)
                    if not block:
                        break
                    out.write(block)
                    received += len(block)
                    if total:
                        report(min(99, received * 100 // total), 'downloading')
        if received < MIN_ZIP_BYTES:
            raise AdbSetupError('The download was much smaller than a real Platform-Tools archive. Check the connection and try again.')
        if not zipfile.is_zipfile(target):
            raise AdbSetupError('The downloaded file was not a valid ZIP archive. Nothing was installed.')
        report(None, 'installing')
        with zipfile.ZipFile(target) as archive:
            bad = archive.testzip()
            if bad is not None:
                raise AdbSetupError('The downloaded archive is damaged (' + bad + '). Nothing was installed.')
            # Extract only the expected platform-tools/ tree, no absolute paths.
            for info in archive.infolist():
                name = info.filename.replace('\\', '/')
                if name.startswith('/') or '..' in name.split('/') or not name.startswith('platform-tools/'):
                    raise AdbSetupError('The archive layout was unexpected. Extraction refused.')
            archive.extractall(base)
        adb = find_adb(base)
        if not adb:
            raise AdbSetupError('Extraction finished but adb was not found in the platform-tools folder.')
        if os.name != 'nt':
            try:
                os.chmod(adb, os.stat(adb).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            except OSError:
                pass
        report(100, 'ready')
        return adb
    except AdbSetupError:
        raise
    except Exception as e:
        raise AdbSetupError('Could not download Platform-Tools: ' + str(e))
    finally:
        try:
            target.unlink()
        except OSError:
            pass
