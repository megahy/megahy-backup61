# Copyright (c) 2026 Marwan Megahy
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License version 3 or (at your option) any later
# version. See LICENSE.txt.
"""Validated, explicit backup selections. Filename filters never prove completeness."""
from pathlib import PurePosixPath
import re

PROVIDERS = ('contacts', 'sms', 'mms', 'call_log')
STORAGE_MODES = ('all', 'media', 'photos', 'videos', 'folder', 'none')
PHOTO_EXTENSIONS = frozenset('.jpg .jpeg .jpe .png .gif .webp .heic .heif .avif .bmp .tif .tiff .dng .raw .nef .cr2 .cr3 .arw .rw2 .orf .raf .pef .srw .svg'.split())
VIDEO_EXTENSIONS = frozenset('.mp4 .m4v .mov .3gp .3g2 .mkv .webm .avi .wmv .flv .mpeg .mpg .mts .m2ts .ts .vob .ogv'.split())
CACHE_NAMES = frozenset(('cache', 'caches', '.cache', 'code_cache', 'thumbnails', '.thumbnails'))


def defaults():
    return dict(storage='all', providers=list(PROVIDERS), folder='', include_hidden=True, include_cache=True, incremental=True)


def folder_scope(value):
    """Return (volume label, volume root, scan root). No private filesystem paths."""
    if not isinstance(value, str) or not value or len(value) > 2048 or any(ord(c) < 32 for c in value):
        raise ValueError('Enter a phone folder path, for example /sdcard/DCIM/Camera')
    if '..' in value.split('/') or not value.startswith('/'):
        raise ValueError('Use an absolute shared-storage folder path without .. segments')
    path = str(PurePosixPath(value))
    if path == '/storage/emulated/0' or path.startswith('/storage/emulated/0/'):
        path = '/sdcard' + path[len('/storage/emulated/0'):]
    if path == '/sdcard' or path.startswith('/sdcard/'):
        return 'Internal storage', '/sdcard/', path.rstrip('/') + '/'
    match = re.match(r'^(/storage/([0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}))(?:/|$)', path)
    if match:
        return 'SD-' + match[2], match[1] + '/', path.rstrip('/') + '/'
    raise ValueError('Choose a folder under /sdcard/ or /storage/XXXX-XXXX/. Private app/system folders are not supported.')


def validate(value=None):
    if value is None:
        return defaults()
    if not isinstance(value, dict) or set(value) - set(defaults()):
        raise ValueError('Invalid backup selection fields')
    result = defaults()
    result.update(value)
    if result['storage'] not in STORAGE_MODES:
        raise ValueError('Choose a supported storage selection')
    providers = result['providers']
    if not isinstance(providers, list) or any(not isinstance(p, str) or p not in PROVIDERS for p in providers) or len(set(providers)) != len(providers):
        raise ValueError('Choose supported provider categories without duplicates')
    if type(result['include_hidden']) is not bool or type(result['include_cache']) is not bool:
        raise ValueError('Hidden/cache selections must be true or false')
    if type(result['incremental']) is not bool:
        raise ValueError('Incremental selection must be true or false')
    if not isinstance(result['folder'], str):
        raise ValueError('Folder path must be text')
    if result['storage'] == 'folder':
        _, _, result['folder'] = folder_scope(result['folder'])
    else:
        result['folder'] = ''
    if result['storage'] == 'none' and not providers:
        raise ValueError('Select at least one storage or provider category')
    result['providers'] = [p for p in PROVIDERS if p in providers]
    return result


def exclusion(path, volume_root, options):
    """Return an explicit exclusion reason or None. No file contents are read."""
    parts = PurePosixPath(path[len(volume_root):]).parts
    if not options['include_hidden'] and any(part.startswith('.') for part in parts):
        return 'hidden'
    if not options['include_cache'] and any(part.casefold() in CACHE_NAMES for part in parts[:-1]):
        return 'cache'
    suffix = PurePosixPath(path).suffix.casefold()
    mode = options['storage']
    if mode == 'photos' and suffix not in PHOTO_EXTENSIONS:
        return 'type'
    if mode == 'videos' and suffix not in VIDEO_EXTENSIONS:
        return 'type'
    if mode == 'media' and suffix not in PHOTO_EXTENSIONS | VIDEO_EXTENSIONS:
        return 'type'
    return None
