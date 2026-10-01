#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 JamosisKlyde and APKBridge contributors
set -euo pipefail

apkbridge_data="${HOME}/.local/share/apkbridge"
apkbridge_bin="${HOME}/.local/bin/apkbridge"
apkbridge_desktop="${HOME}/.local/share/applications/apkbridge.desktop"
apkbridge_icon="${HOME}/.local/share/icons/hicolor/scalable/apps/apkbridge.svg"

rm -f -- "${apkbridge_bin}" "${apkbridge_desktop}" "${apkbridge_icon}"

if [[ "${1:-}" == "--purge" ]]; then
  rm -rf -- "${apkbridge_data}"
  echo "APKBridge and its saved settings, records, logs, and private Python environment were removed."
else
  rm -rf -- "${apkbridge_data}/app"
  echo "APKBridge was removed. Saved settings, records, logs, and the private Python environment were kept at:"
  echo "  ${apkbridge_data}"
  echo "Run ./uninstall.sh --purge only if you also want those APKBridge files removed."
fi

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "${HOME}/.local/share/applications" >/dev/null 2>&1 || true
fi
