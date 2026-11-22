@echo off
setlocal
cd /d "%~dp0"
rem Copyright (c) 2026 CableVault contributors and Marwan Megahy
rem SPDX-License-Identifier: GPL-3.0-or-later
rem Licensed under the GNU General Public License version 3 or later. See LICENSE.txt.
title megahy-backup - Android USB backup 0.3.1-rc2
if not exist "%~dp0runtime\python.exe" (
  echo The bundled runtime is missing. Extract the whole ZIP first.
  pause
  exit /b 1
)
"%~dp0runtime\python.exe" "%~dp0megahy_backup.py"
if errorlevel 1 (
  echo.
  echo megahy-backup could not start. This package requires a 64-bit Windows PC.
  echo Keep this message for troubleshooting. See README.txt.
  pause
)
