# Support and troubleshooting

Report reproducible APKBridge problems through [GitHub Issues](https://github.com/JamosisKlyde/ApkBridge/issues).
Support is best effort; no response time or compatibility guarantee is offered.

## Include in a report

- APKBridge version, Linux distribution/version, desktop, and Wayland/X11 session.
- Waydroid version, CPU architecture, and whether ARM translation is enabled.
- Android app name/version and package ID, expected result, actual result, and steps.
- A redacted Activity Log or diagnostic report and an optional screenshot.

Do not attach copyrighted APKs, account credentials, session tokens, or private
viewing history. Diagnostics can contain usernames, local paths, and app IDs.
For vulnerabilities, follow [SECURITY.md](SECURITY.md).

## Common problems

| Problem | What to try |
| --- | --- |
| APKBridge will not open | Run `~/.local/bin/apkbridge` in a terminal and include its error. Check Python 3.10+ and PyQt6 availability. |
| Waydroid is not ready | Open **Setup & Repair**, install Waydroid if needed, initialize Android, and start the session. Use a Wayland desktop. |
| Package name was not detected | Run `waydroid app list`, find the installed app's package name, and enter it in APKBridge. |
| Fullscreen moves a small window | Confirm version 0.1.3 or later, choose the app package, and use **Enter Fullscreen**. Accept the Android restart. |
| Need to leave fullscreen | Alt+Tab back to APKBridge and use **Exit Fullscreen**. This can close running Android apps. |
| Portrait layout or side bars remain | The app may enforce its own orientation. APKBridge does not force stretching or override app orientation. |
| ARM-only APK fails on x86-64 | Review the optional ARM compatibility controls. Translation is not guaranteed to make every app work. |
| Video is black or protected playback fails | Try the Video / Black-screen Test profile. App DRM, codecs, or container restrictions can still prevent playback. |
| No menu icon after installation | Run `~/.local/bin/apkbridge`; check that the installer completed, then refresh the desktop session if necessary. |

Changing a launch profile or Android display mode can restart Waydroid and close
all Android apps. Save progress first. App-specific failures may need reporting
to the app developer or [Waydroid](https://github.com/waydroid/waydroid/issues).
