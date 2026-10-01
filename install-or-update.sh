#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 JamosisKlyde and APKBridge contributors
set -euo pipefail

apkbridge_here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
apkbridge_data="${HOME}/.local/share/apkbridge"
apkbridge_app="${apkbridge_data}/app"
apkbridge_venv="${apkbridge_data}/venv"
apkbridge_bin_dir="${HOME}/.local/bin"
apkbridge_desktop_dir="${HOME}/.local/share/applications"
apkbridge_icon_dir="${HOME}/.local/share/icons/hicolor/scalable/apps"
apkbridge_versions="${apkbridge_data}/versions"
apkbridge_version="0.1.3"

if ! command -v python3 >/dev/null 2>&1; then
  echo "APKBridge needs Python 3. Install Python, then run this installer again."
  exit 1
fi

mkdir -p "${apkbridge_data}" "${apkbridge_bin_dir}" "${apkbridge_desktop_dir}" "${apkbridge_icon_dir}" "${apkbridge_versions}" "${apkbridge_data}/logs"

apkbridge_python="$(command -v python3)"
if ! "${apkbridge_python}" -c 'from PyQt6.QtWidgets import QApplication' >/dev/null 2>&1; then
  echo "PyQt6 was not found. Installing a private APKBridge Python environment..."
  if [[ ! -x "${apkbridge_venv}/bin/python3" ]]; then
    if ! "${apkbridge_python}" -m venv "${apkbridge_venv}"; then
      echo
      echo "Could not create APKBridge's private Python environment."
      echo "Fedora: sudo dnf install python3-qt6 python3-pip"
      echo "Ubuntu: sudo apt install python3-pyqt6 python3-venv"
      echo "Arch: sudo pacman -S python-pyqt6"
      exit 1
    fi
  fi
  if ! "${apkbridge_venv}/bin/python3" -c 'from PyQt6.QtWidgets import QApplication' >/dev/null 2>&1; then
    "${apkbridge_venv}/bin/python3" -m pip install --disable-pip-version-check 'PyQt6>=6.5,<7'
  fi
  apkbridge_python="${apkbridge_venv}/bin/python3"
fi

if [[ -d "${apkbridge_app}" ]]; then
  apkbridge_stamp="$(date +%Y%m%d-%H%M%S)"
  cp -a "${apkbridge_app}" "${apkbridge_versions}/app-${apkbridge_stamp}"
  echo "Saved the previous APKBridge program files in ${apkbridge_versions}/app-${apkbridge_stamp}"
fi

rm -rf -- "${apkbridge_app}.new"
mkdir -p "${apkbridge_app}.new"
cp -a "${apkbridge_here}/app/." "${apkbridge_app}.new/"
printf '{\n  "app_id": "apkbridge",\n  "version": "%s"\n}\n' "${apkbridge_version}" > "${apkbridge_app}.new/version.json"
rm -rf -- "${apkbridge_app}"
mv "${apkbridge_app}.new" "${apkbridge_app}"
chmod 0755 "${apkbridge_app}/apkbridge.py" "${apkbridge_app}/bridge_core.py" "${apkbridge_app}/arm_helper.py"

install -m 0755 "${apkbridge_here}/packaging/apkbridge" "${apkbridge_bin_dir}/apkbridge"
install -m 0644 "${apkbridge_app}/apkbridge.svg" "${apkbridge_icon_dir}/apkbridge.svg"
sed "s|@LAUNCHER@|${apkbridge_bin_dir}/apkbridge|g" "${apkbridge_here}/packaging/apkbridge.desktop.in" > "${apkbridge_desktop_dir}/apkbridge.desktop"
chmod 0644 "${apkbridge_desktop_dir}/apkbridge.desktop"

if command -v desktop-file-validate >/dev/null 2>&1; then
  desktop-file-validate "${apkbridge_desktop_dir}/apkbridge.desktop" || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "${apkbridge_desktop_dir}" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -f -t "${HOME}/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi
if command -v xdg-mime >/dev/null 2>&1; then
  xdg-mime default apkbridge.desktop application/vnd.android.package-archive >/dev/null 2>&1 || true
fi

echo
echo "========================================"
echo " APKBridge ${apkbridge_version} installed"
echo "========================================"
echo "Open APKBridge from the application menu."
echo "Your settings, Android app records, and logs are stored outside the replaceable program folder."
echo "Waydroid setup is available inside APKBridge under Setup & Repair."
echo
echo "Command-line launcher: ${apkbridge_bin_dir}/apkbridge"
