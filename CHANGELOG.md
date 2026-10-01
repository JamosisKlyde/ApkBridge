# Repository and release information update — 2026-09-30

- Added GPL-3.0-only licensing, copyright notices, and third-party license information.
- Added requirements, support, security reporting, privacy, and contributor documentation.
- Added issue/PR templates and read-only CI for Python 3.10 and 3.12.
- Added legal attachments and a source ZIP with notices to v0.1.3.
- The v0.1.3 tag, application behavior, original installer, and its checksum remain unchanged.

# 0.1.3

- Fullscreen now switches Waydroid out of multi-window mode and clears fixed display dimensions.
- Exit restores the selected app saved profile dimensions and window mode.
- Display changes relaunch the app and warn that Android apps may close.
- Preserve compatibility settings when changing display mode.
- Report session-stop failure rather than continue with a stale display.

# 0.1.2

- Added Enter Fullscreen and Exit Fullscreen buttons for running Android windows.
- Display changes save the per-app preference without restarting Waydroid.
- Added org.waydroid window-class matching.
- Explicit display actions report an error when KDE is unavailable.

# 0.1.1

- Added saved KDE fullscreen launch checkbox.
- Added Ctrl+Alt+F11 toggle for Waydroid windows.
- App-menu shortcuts honor the saved fullscreen preference.

# Changelog

## 0.1.0 — initial private preview

- Added a dedicated Linux desktop interface for Android APKs.
- Added Waydroid install, initialization, session, app-install, app-launch, and app-removal controls.
- Added APK integrity, native ABI, and likely ARM-translation checks.
- Added six desktop launch profiles and package-specific mouse/touch and fake-Wi-Fi controls.
- Added managed Android app records and per-app Linux shortcuts.
- Added diagnostics and a non-destructive recent-log collector.
- Added an explicit, reversible libndk ARM compatibility workflow with configuration snapshots.
