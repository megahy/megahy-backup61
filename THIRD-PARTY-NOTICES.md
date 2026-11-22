# Third-party notices

## Existing application attribution and license
The v0.3.0 package carried an MIT license crediting CableVault contributors. The owner chose GPLv3-or-later for megahy-backup on 2026-11-22. The MIT license permits this: the full MIT notice is retained verbatim in `NOTICE.txt`, and the combined work is licensed under GPLv3 (MIT is GPL-compatible). This is not a claim that Marwan wrote or owns third-party dependencies. No external application libraries were added to the runtime code.

## Bundled CPython runtime
The Windows package includes CPython 3.14.10, x64 embeddable distribution. Its complete upstream license and dependency notices are retained verbatim in `runtime/LICENSE.txt`, including notices for components shipped in that distribution. The CPython (PSF) license is permissive and GPL-compatible, so bundling it with a GPLv3 application is permitted. Do not remove them when redistributing the Windows package. Source-only packages omit this runtime.

Provenance: downloaded from the official release page:
https://www.python.org/downloads/release/python-31410/
Official download observed there:
https://www.python.org/ftp/python/3.14.10/python-3.14.10-embed-amd64.zip

On 2026-11-22 all 37 files in the original bundled runtime matched this official download byte-for-byte. Observed ZIP SHA-256: `90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159`. This is a byte-comparison provenance check, not independent signature validation, a malware certification or a Windows execution test.

License reference: https://docs.python.org/3/license.html
Embedding reference: https://docs.python.org/3/using/windows.html

## Google Platform-Tools / ADB
Not bundled. Users must download them from Google's official page and review its terms themselves. SDK terms sections 3.4 and 3.5 restrict redistribution subject to exceptions for open-source components. This package avoids claiming a redistribution right for Google's complete prebuilt Platform-Tools ZIP. A future separately built ADB binary would require its own source/dependency/license audit.

https://developer.android.com/tools/releases/platform-tools
https://developer.android.com/studio/terms

## Development-only tools
Playwright/Chromium are used only for optional synthetic UI tests and are not bundled. A future CI workflow may obtain Python through GitHub's setup-python action. These tools retain their own licenses. No remote font, image, analytics service or CDN code is loaded by the app interface.

## Names
Google, Android, Python and device-maker names identify compatibility only. This project is not endorsed by those organizations. Third-party trademarks and copyrights remain with their owners.
