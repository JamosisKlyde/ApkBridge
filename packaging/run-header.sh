#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 JamosisKlyde and APKBridge contributors
set -euo pipefail

apkbridge_archive_line="$(awk '/^__APKBRIDGE_ARCHIVE_BELOW__$/ { print NR + 1; exit }' "$0")"
if [[ -z "${apkbridge_archive_line}" ]]; then
  echo "APKBridge installer payload could not be located."
  exit 1
fi

if [[ "${1:-}" == "--extract-only" ]]; then
  if [[ -z "${2:-}" ]]; then
    echo "Usage: $0 --extract-only DIRECTORY"
    exit 1
  fi
  mkdir -p -- "$2"
  tail -n +"${apkbridge_archive_line}" "$0" | tar -xz -C "$2"
  echo "APKBridge installer extracted to: $2"
  exit 0
fi

apkbridge_temp="$(mktemp -d)"
cleanup_apkbridge_installer() {
  rm -rf -- "${apkbridge_temp}"
}
trap cleanup_apkbridge_installer EXIT

tail -n +"${apkbridge_archive_line}" "$0" | tar -xz -C "${apkbridge_temp}"
chmod +x "${apkbridge_temp}/APKBridge-0.1.3/install-or-update.sh"
"${apkbridge_temp}/APKBridge-0.1.3/install-or-update.sh"
exit 0

__APKBRIDGE_ARCHIVE_BELOW__
