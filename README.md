# APKBridge

Run Android APKs on Linux through Waydroid. Current preview: **0.1.3**.

[Download the Linux installer](https://github.com/JamosisKlyde/ApkBridge/raw/refs/heads/main/downloads/APKBridge-0.1.3_Display_Fix.run) · [Changelog](CHANGELOG.md)

```bash
bash ~/Downloads/APKBridge-0.1.3_Display_Fix.run
```

## Fullscreen update

Close APKBridge and run this installer over the existing version. Android data and app mappings are preserved.

On Run APK, keep your app's package name selected and click Enter Fullscreen. Confirm the Android session restart. APKBridge switches off Waydroid multi-window mode, clears the fixed width/height overrides so Waydroid can size the display, and relaunches the app. KDE fullscreen remains a complementary window control.

Use Alt+Tab to return to APKBridge and click Exit Fullscreen. It restores the saved launch profile's window mode and dimensions and relaunches the app. Save work first: switching modes affects the entire Waydroid session and may close all Android apps. Compatibility settings are retained.

This corrects an error in 0.1.1/0.1.2: those versions changed the KDE window state while keeping Android in multi-window mode at a fixed resolution. A portrait-only app can still retain side bars or portrait layout. No forced stretching or orientation override is applied.

Tested with backend regression tests, simulated KWin windows, and offscreen Qt button checks. Actual KDE/Waydroid rendering cannot be verified in the build environment.

Reference: https://docs.waydro.id/usage/waydroid-prop-options

## About

APKBridge is a Linux desktop program for installing and running Android APKs as desktop applications. It uses Waydroid for the Android container and adds a focused launcher, compatibility profiles, app shortcuts, APK checks, session controls, and diagnostics.

APKBridge is separate from ExeBridge. Installing it does not replace or modify ExeBridge.

## What works in this build

- Drag in or browse for a single `.apk` file.
- Validate the APK container and inspect bundled native CPU libraries.
- Detect APKs that will probably need ARM translation on an x86-64 computer.
- Install and launch APKs through Waydroid.
- Remember imported apps, source APKs, native ABIs, and launch profiles.
- Create normal Linux application-menu shortcuts for individual Android apps.
- Use six launch profiles:
  - Desktop Balanced
  - Desktop 16:9
  - Phone Portrait
  - TV / Full HD
  - Gaming
  - Video / Black-screen Test
- Control mouse-as-touch, fake Wi-Fi, and RGBA/BGRA inversion per launch.
- Install, initialize, start, and stop Waydroid from the interface.
- Create non-destructive diagnostic reports with recent Waydroid logs.
- Optionally install or remove the libndk ARM translator with an explicit confirmation and configuration snapshot.

## Important limits

- This preview accepts single APK files. XAPK/APKS split bundles are not enabled yet.
- Waydroid requires a Wayland desktop session for normal integration.
- ARM translation improves compatibility but cannot make every ARM-only app work.
- DRM, Play Integrity/SafetyNet, anti-cheat, protected streaming video, and hardware-specific applications can still reject the container.
- The Video / Black-screen Test profile changes presentation properties; it cannot repair application-level DRM or a missing codec.
- Installing libndk is an advanced, opt-in system-image modification. APKBridge downloads the current GPL-licensed `casualsnek/waydroid_script` when you approve it, records the exact source revision, and does not bundle proprietary translation files.

## Install

1. Download this repository using **Code → Download ZIP**, then extract it.
2. Open the extracted repository folder.
3. Right-click inside the folder and choose **Open in Terminal**.
4. Run:

   ```bash
   chmod +x install-or-update.sh uninstall.sh
   ./install-or-update.sh
   ```

5. Open **APKBridge** from the application menu.
6. If Waydroid is not ready, open **Setup & Repair** inside APKBridge and follow the buttons in order.

The installer uses the system PyQt6 package when available. If PyQt6 is missing, it creates a private Python environment under `~/.local/share/apkbridge/venv` and installs PyQt6 there without replacing system Python packages.

## Distribution notes

- Fedora: APKBridge can install the official `waydroid` package with `dnf`.
- Bazzite, Kinoite, and Silverblue: APKBridge uses `rpm-ostree` for Waydroid. Reboot after layering it, then return to APKBridge to initialize Android.
- Ubuntu/Debian: APKBridge can install Waydroid after the appropriate Waydroid repository is available. Older releases may require the repository setup described in the official Waydroid documentation.
- Arch: Waydroid availability depends on the enabled repositories/AUR setup.

## Uninstall

From the extracted folder, run:

```bash
./uninstall.sh
```

That removes the program and menu entry while retaining settings and logs. To remove APKBridge's saved files as well:

```bash
./uninstall.sh --purge
```

Uninstalling APKBridge does not uninstall Waydroid or delete Waydroid's Android applications and data.

## Data locations

- Program: `~/.local/share/apkbridge/app`
- Settings and app records: `~/.local/share/apkbridge`
- Logs and diagnostics: `~/.local/share/apkbridge/logs`
- Launcher: `~/.local/bin/apkbridge`
- App-menu entry: `~/.local/share/applications/apkbridge.desktop`

## Source status

This is a development preview. No open-source license has been selected for APKBridge yet.

Run the regression tests with Python 3 and Node.js installed:

```bash
python3 -m unittest discover -s tests -v
```
