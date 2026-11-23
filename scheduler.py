# Copyright (c) 2026 Marwan Megahy
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License version 3 or (at your option) any later
# version. See LICENSE.txt.
"""Windows Task Scheduler integration for unattended backups (schtasks only)."""
import os
from pathlib import Path
import re
import subprocess
import sys

TASK_NAME = 'megahy-backup-auto'
FREQUENCIES = ('daily', 'weekly')


class ScheduleError(Exception):
    pass


def _validate_time(value):
    if not isinstance(value, str) or not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d', value):
        raise ScheduleError('Use a 24-hour time such as 21:30')
    return value


def _run_schtasks(args):
    result = subprocess.run(['schtasks'] + args, capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=60,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    return result.returncode, (result.stdout or '') + (result.stderr or '')


def install(base, frequency, time_str):
    """Create or replace the Windows scheduled task. Returns the command used."""
    if os.name != 'nt':
        raise ScheduleError('One-click scheduling is built into the Windows package. On this system, run megahy_backup.py --auto from your own scheduler.')
    if frequency not in FREQUENCIES:
        raise ScheduleError('Choose a daily or weekly schedule')
    time_str = _validate_time(time_str)
    base = Path(base)
    bundled = base / 'runtime' / 'python.exe'
    exe = str(bundled) if bundled.is_file() else str(Path(sys.executable).resolve())
    script = str((base / 'megahy_backup.py').resolve())
    command = '"' + exe + '" "' + script + '" --auto'
    code, text = _run_schtasks(['/Create', '/F', '/TN', TASK_NAME, '/SC', frequency.upper(),
                                '/ST', time_str, '/TR', command])
    if code:
        raise ScheduleError('Windows could not create the task: ' + text.strip()[:600])
    return {'task': TASK_NAME, 'frequency': frequency, 'time': time_str, 'command': command}


def remove():
    if os.name != 'nt':
        raise ScheduleError('Scheduling is only managed on Windows.')
    code, text = _run_schtasks(['/Delete', '/F', '/TN', TASK_NAME])
    if code and 'cannot find' not in text.lower() and 'not exist' not in text.lower():
        raise ScheduleError('Windows could not remove the task: ' + text.strip()[:600])
    return True


def status():
    """Return True when the scheduled task currently exists (Windows only)."""
    if os.name != 'nt':
        return False
    code, _ = _run_schtasks(['/Query', '/TN', TASK_NAME])
    return code == 0
