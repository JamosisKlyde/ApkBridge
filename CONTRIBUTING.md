# Contributing to APKBridge

Bug reports, documentation fixes, and focused pull requests are welcome. Discuss
large behavioral changes in an issue first. Keep discussion respectful and
specific. Maintainer: [JamosisKlyde](https://github.com/JamosisKlyde).

## Development

Use Linux, Python 3.10+, and Node.js for tests. Running the GUI also requires
PyQt6. Waydroid and a Wayland desktop are needed to test Android apps; the
fullscreen integration targets KDE Plasma 6.

```bash
git clone https://github.com/JamosisKlyde/ApkBridge.git
cd ApkBridge
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app/apkbridge.py
```

The app uses normal per-user settings even when run from source. Use a separate
test account or VM when testing installers or Android session changes. Do not
run the GUI as root.

## Validation

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q app
bash -n install-or-update.sh uninstall.sh packaging/apkbridge packaging/run-header.sh
```

Tests simulate Android/KWin interactions. A passing test does not establish
hardware, compositor, or Android app compatibility. For relevant UI/display
changes, include what you tested on a real desktop.

## Pull requests

- Explain the problem, resulting behavior, and validation performed.
- Add focused tests when behavior or error handling changes.
- Preserve per-app settings and avoid unnecessary Android restarts.
- Do not commit APKs, Android images, translation binaries, logs, tokens, or
  machine-specific paths.
- Preserve the GPL notices and document added dependencies and their licenses.
- Do not change published tags or installer assets without an explicit release
  decision; see [RELEASING.md](RELEASING.md).

By contributing, you agree to license your contribution under this project's
GPL-3.0-only license. Only contribute material you have the right to submit.
