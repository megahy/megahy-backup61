# Privacy

Backups stay at the PC destination selected by the user. The application contains no backup-upload or analytics function. Its interface binds to `127.0.0.1`, with a per-run token. Keep the console URL private. Anyone with access to the PC can potentially access local backup data; loopback and a token do not make a compromised PC safe.

Backups are not encrypted by this app. File inventories and reports can contain device identifiers, paths, filenames, contact details and message text. Do not commit or attach unredacted backups/reports to public issues. The example data in tests is synthetic.

The app issues read/copy device commands, not deletion, installation, permission grants, root, reset or restore. A live phone is not a snapshot. ADB itself starts a local service and may store its usual host authorization state. Google downloads, operating-system behavior, device drivers and the user's browser are separate software.
