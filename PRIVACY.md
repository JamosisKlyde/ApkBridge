# Data and network behavior

APKBridge has no built-in analytics, advertising, account registration, or
automatic diagnostic upload. This statement covers APKBridge's code, not the
Android apps or external services used through it.

## Local data

- `~/.local/share/apkbridge/`: UI settings, package IDs, app names, APK paths and
  hashes, launch profiles, and timestamps.
- `~/.local/share/apkbridge/logs/`: command output, Activity Logs, and diagnostics.
- `~/.local/share/apkbridge/versions/`: previous installed program files.
- `~/.local/share/applications/`: launcher and per-app shortcuts.
- Optional ARM operations also use `/var/cache/apkbridge/`,
  `/var/lib/apkbridge/`, and `/var/log/apkbridge-arm.log`.

Logs and reports can contain usernames, local file paths, package IDs, device
information, and output from Waydroid. Review and redact them before sharing.

## Network use

The installer can download PyQt6 and its dependencies from the configured pip
index. Setup uses distribution package repositories and Waydroid image
downloads. The optional ARM helper fetches the community GitHub repository,
Python dependencies, and upstream payloads. Android apps have their own network
behavior and privacy policies.

APKBridge does not automatically publish your APKs or logs to GitHub. Reports
you choose to post in public GitHub Issues are public.

## Removal

Normal uninstall preserves APKBridge settings and logs. `uninstall.sh --purge`
removes the user's `~/.local/share/apkbridge` directory too. Neither option
removes Waydroid, Android apps/data, generated per-app shortcuts, or root-owned
ARM helper files. Manage those separately. Purging APKBridge data is irreversible.
