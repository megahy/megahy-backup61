# Copyright (c) 2026 Marwan Megahy
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License version 3 or (at your option) any later
# version. See LICENSE.txt.
"""Local settings and named profiles. Nothing is uploaded; one JSON file on the PC."""
import json
from pathlib import Path
import threading

_lock = threading.Lock()

FIELDS = ('destination', 'selection', 'theme', 'language', 'profiles', 'schedule')


def _path(base):
    return Path(base) / 'settings.json'


def load(base):
    """Return stored settings, or defaults. A corrupt file is replaced by defaults."""
    data = {}
    try:
        raw = json.loads(_path(base).read_text(encoding='utf-8'))
        if isinstance(raw, dict):
            data = raw
    except Exception:
        data = {}
    result = {
        'destination': '',
        'selection': None,
        'theme': 'light',
        'language': 'en',
        'profiles': {},
        'schedule': {},
    }
    if isinstance(data.get('destination'), str):
        result['destination'] = data['destination'][:2048]
    if isinstance(data.get('selection'), dict):
        result['selection'] = data['selection']
    if data.get('theme') in ('light', 'dark'):
        result['theme'] = data['theme']
    if data.get('language') in ('en', 'ar'):
        result['language'] = data['language']
    if isinstance(data.get('profiles'), dict):
        for name, profile in data['profiles'].items():
            if isinstance(name, str) and 0 < len(name) <= 60 and isinstance(profile, dict):
                result['profiles'][name] = {
                    'destination': profile.get('destination') if isinstance(profile.get('destination'), str) else '',
                    'selection': profile.get('selection') if isinstance(profile.get('selection'), dict) else None,
                }
    if isinstance(data.get('schedule'), dict):
        result['schedule'] = data['schedule']
    return result


def save(base, data):
    """Atomically write settings. Only known fields are kept."""
    with _lock:
        clean = {k: data.get(k) for k in FIELDS}
        tmp = _path(base).with_name('settings.json.tmp')
        tmp.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(_path(base))
