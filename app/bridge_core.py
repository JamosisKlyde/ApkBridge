#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 JamosisKlyde and APKBridge contributors
"""Backend and command-line interface for APKBridge.

APKBridge is a desktop front-end for Waydroid.  This module intentionally keeps
all container operations outside the Qt interface so they can be tested, logged,
and used by desktop shortcuts.
"""

from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import time
import zipfile
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

VERSION = "0.1.3"
APPDATA = Path.home() / ".local" / "share" / "apkbridge"
STATE_FILE = APPDATA / "state.json"
LOG_DIR = APPDATA / "logs"
CORE_LOG = LOG_DIR / "apkbridge.log"
SHORTCUT_DIR = Path.home() / ".local" / "share" / "applications"
PACKAGE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+$")
PACKAGE_IN_TEXT_RE = re.compile(r"\b(?:[A-Za-z][A-Za-z0-9_]*\.)+[A-Za-z0-9_]+\b")


@dataclass(frozen=True)
class Profile:
    name: str
    width: int
    height: int
    multi_window: bool = True
    fake_touch: bool = True
    fake_wifi: bool = False
    keep_awake: bool = False
    no_presentation: bool = False
    cursor_force_shm: bool = False
    use_subsurface: bool | None = None
    invert_colors: bool = False
    description: str = ""


PROFILES: dict[str, Profile] = {
    "Desktop Balanced": Profile(
        "Desktop Balanced", 1280, 800,
        description="A desktop-sized Android window with mouse clicks translated as touch.",
    ),
    "Desktop 16:9": Profile(
        "Desktop 16:9", 1280, 720,
        description="A widescreen desktop window for media and landscape apps.",
    ),
    "Phone Portrait": Profile(
        "Phone Portrait", 540, 960,
        description="A tall phone-shaped window for apps that reject tablet layouts.",
    ),
    "TV / Full HD": Profile(
        "TV / Full HD", 1920, 1080, fake_touch=False, fake_wifi=True,
        description="A 1080p landscape profile for Android TV interfaces.",
    ),
    "Gaming": Profile(
        "Gaming", 1280, 720, fake_wifi=True, keep_awake=True,
        description="Widescreen, fake Wi-Fi, touch-style mouse input, and no container sleep.",
    ),
    "Video / Black-screen Test": Profile(
        "Video / Black-screen Test", 1280, 720, fake_wifi=True,
        no_presentation=True, cursor_force_shm=True, use_subsurface=False,
        description="Tests conservative Wayland presentation settings for blank video windows.",
    ),
}


class BridgeError(RuntimeError):
    """A user-facing APKBridge operation error."""


def _ensure_dirs() -> None:
    for path in (APPDATA, LOG_DIR, SHORTCUT_DIR):
        path.mkdir(parents=True, exist_ok=True)


def log(message: str) -> None:
    _ensure_dirs()
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(line, flush=True)
    try:
        with CORE_LOG.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def run(
    command: Iterable[object],
    *,
    timeout: int = 120,
    check: bool = False,
    capture: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd = [str(part) for part in command]
    log("$ " + " ".join(shlex.quote(part) for part in cmd))
    try:
        result = subprocess.run(
            cmd,
            text=True,
            capture_output=capture,
            timeout=timeout,
            env=env,
            check=False,
        )
    except FileNotFoundError as exc:
        raise BridgeError(f"Required command is missing: {cmd[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise BridgeError(f"Command timed out after {timeout} seconds: {cmd[0]}") from exc
    if capture:
        if result.stdout.strip():
            log(result.stdout.strip())
        if result.stderr.strip():
            log(result.stderr.strip())
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "command failed").strip()
        raise BridgeError(detail)
    return result


def which(name: str) -> str:
    return shutil.which(name) or ""


def read_os_release() -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        for raw in Path("/etc/os-release").read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" not in raw or raw.lstrip().startswith("#"):
                continue
            key, value = raw.split("=", 1)
            values[key] = value.strip().strip('"')
    except OSError:
        pass
    return values


def cpu_info() -> dict[str, Any]:
    vendor = "unknown"
    model = platform.processor() or "unknown"
    flags: set[str] = set()
    try:
        text = Path("/proc/cpuinfo").read_text(errors="ignore")
        match = re.search(r"^vendor_id\s*:\s*(.+)$", text, re.MULTILINE)
        if match:
            vendor = match.group(1).strip()
        match = re.search(r"^model name\s*:\s*(.+)$", text, re.MULTILINE)
        if match:
            model = match.group(1).strip()
        match = re.search(r"^flags\s*:\s*(.+)$", text, re.MULTILINE)
        if match:
            flags = set(match.group(1).split())
    except OSError:
        pass
    return {
        "architecture": platform.machine() or "unknown",
        "vendor": vendor,
        "model": model,
        "sse4_2": "sse4_2" in flags,
    }


def load_state() -> dict[str, Any]:
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("schema", 1)
            data.setdefault("apps", {})
            data.setdefault("apk_hashes", {})
            return data
    except (OSError, ValueError, TypeError):
        pass
    return {"schema": 1, "apps": {}, "apk_hashes": {}}


def save_state(state: dict[str, Any]) -> None:
    _ensure_dirs()
    temp = STATE_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    try:
        temp.chmod(0o600)
    except OSError:
        pass
    temp.replace(STATE_FILE)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_package(package: str) -> str:
    package = str(package or "").strip()
    if not PACKAGE_RE.fullmatch(package):
        raise BridgeError(f"Invalid Android package name: {package or '(blank)'}")
    return package


def package_from_aapt(apk: Path) -> dict[str, str]:
    for tool_name in ("aapt2", "aapt"):
        tool = which(tool_name)
        if not tool:
            continue
        result = run([tool, "dump", "badging", apk], timeout=45)
        if result.returncode != 0:
            continue
        text = result.stdout
        package_match = re.search(
            r"package:\s+name='([^']+)'(?:\s+versionCode='([^']*)')?(?:\s+versionName='([^']*)')?",
            text,
        )
        sdk_match = re.search(r"sdkVersion:'([^']+)'", text)
        label_match = re.search(r"application-label(?:-[^:]+)?:'([^']*)'", text)
        if package_match:
            return {
                "package": package_match.group(1) or "",
                "version_code": package_match.group(2) or "",
                "version_name": package_match.group(3) or "",
                "min_sdk": sdk_match.group(1) if sdk_match else "",
                "label": label_match.group(1) if label_match else "",
            }
    return {"package": "", "version_code": "", "version_name": "", "min_sdk": "", "label": ""}


def analyze_apk(apk_value: str | Path, *, full_hash: bool = True) -> dict[str, Any]:
    apk = Path(apk_value).expanduser().resolve()
    if not apk.is_file():
        raise BridgeError(f"APK not found: {apk}")
    if apk.suffix.lower() != ".apk":
        raise BridgeError("APKBridge 0.1.0 accepts single .apk files. XAPK/APKS bundles are not enabled yet.")
    if not zipfile.is_zipfile(apk):
        raise BridgeError("The selected file is not a valid APK/ZIP container.")

    abis: set[str] = set()
    native_files = 0
    with zipfile.ZipFile(apk) as archive:
        bad_member = archive.testzip()
        if bad_member:
            raise BridgeError(f"The APK is damaged near: {bad_member}")
        for item in archive.infolist():
            parts = item.filename.split("/")
            if len(parts) >= 3 and parts[0] == "lib" and item.filename.endswith(".so"):
                abis.add(parts[1])
                native_files += 1

    details = package_from_aapt(apk)
    host = (platform.machine() or "").lower()
    arm_abis = {"armeabi", "armeabi-v7a", "arm64-v8a"}
    x86_abis = {"x86", "x86_64"}
    requires_translation = bool(abis and host in {"x86_64", "amd64", "x86"} and abis <= arm_abis)
    incompatible_native = bool(abis and host in {"x86_64", "amd64", "x86"} and not (abis & x86_abis) and not requires_translation)
    digest = sha256_file(apk) if full_hash else ""
    return {
        "path": str(apk),
        "file_name": apk.name,
        "size_bytes": apk.stat().st_size,
        "sha256": digest,
        "package": details["package"],
        "label": details["label"] or apk.stem,
        "version_name": details["version_name"],
        "version_code": details["version_code"],
        "min_sdk": details["min_sdk"],
        "native_abis": sorted(abis),
        "native_library_count": native_files,
        "host_architecture": host or "unknown",
        "requires_arm_translation": requires_translation,
        "incompatible_native_architecture": incompatible_native,
    }


def waydroid_status_text() -> str:
    if not which("waydroid"):
        return ""
    result = run(["waydroid", "status"], timeout=20)
    return (result.stdout + "\n" + result.stderr).strip()


def waydroid_version() -> str:
    if not which("waydroid"):
        return ""
    result = run(["waydroid", "--version"], timeout=20)
    text = (result.stdout + " " + result.stderr).strip()
    match = re.search(r"(\d+\.\d+(?:\.\d+)?)", text)
    return match.group(1) if match else text


def waydroid_initialized() -> bool:
    config = Path("/var/lib/waydroid/waydroid.cfg")
    images = Path("/var/lib/waydroid/images")
    return config.is_file() and images.is_dir()


def current_native_bridge() -> str:
    config = Path("/var/lib/waydroid/waydroid.cfg")
    try:
        parser = configparser.ConfigParser()
        parser.read(config)
        bridge = parser.get("properties", "ro.dalvik.vm.native.bridge", fallback="").strip().lower()
        if "libndk" in bridge:
            return "libndk"
        if "houdini" in bridge:
            return "libhoudini"
    except (OSError, configparser.Error):
        pass
    return "none"


def _status_flag(text: str, label: str) -> str:
    match = re.search(rf"^{re.escape(label)}\s*:\s*([^\n]+)", text, re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip().lower() if match else "unknown"


def status() -> dict[str, Any]:
    installed = bool(which("waydroid"))
    text = waydroid_status_text() if installed else ""
    os_release = read_os_release()
    session_type = os.environ.get("XDG_SESSION_TYPE", "unknown")
    result = {
        "apkbridge_version": VERSION,
        "waydroid_installed": installed,
        "waydroid_initialized": waydroid_initialized() if installed else False,
        "waydroid_version": waydroid_version() if installed else "",
        "waydroid_status": text,
        "session": _status_flag(text, "Session") if installed else "missing",
        "container": _status_flag(text, "Container") if installed else "missing",
        "session_type": session_type,
        "wayland": session_type.lower() == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY")),
        "native_bridge": current_native_bridge() if installed else "none",
        "cpu": cpu_info(),
        "distribution": os_release.get("PRETTY_NAME") or os_release.get("NAME") or "Unknown Linux",
        "distribution_id": os_release.get("ID", "unknown"),
        "immutable": bool(which("rpm-ostree")),
    }
    return result


def ensure_session(timeout: int = 50) -> None:
    if not which("waydroid"):
        raise BridgeError("Waydroid is not installed. Open Setup in APKBridge first.")
    if not waydroid_initialized():
        raise BridgeError("Waydroid is installed but not initialized. Open Setup in APKBridge first.")
    text = waydroid_status_text().lower()
    if _status_flag(text, "Session") == "running":
        return
    log("Starting the Waydroid session in the background")
    subprocess.Popen(
        ["waydroid", "session", "start"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(1)
        text = waydroid_status_text().lower()
        if _status_flag(text, "Session") == "running":
            return
    result = run(["waydroid", "app", "list"], timeout=20)
    if result.returncode == 0:
        return
    raise BridgeError("The Waydroid session did not become ready. Start Waydroid once from the application menu, then retry.")


def stop_session() -> dict[str, bool]:
    if not which("waydroid"):
        return {"stopped": True}
    result = run(["waydroid", "session", "stop"], timeout=40)
    return {"stopped": result.returncode == 0}


def parse_app_list(text: str) -> dict[str, str]:
    apps: dict[str, str] = {}
    name = ""
    for raw in (text or "").splitlines():
        line = raw.strip()
        name_match = re.match(r"(?:Name|name)\s*:\s*(.+)", line)
        if name_match:
            name = name_match.group(1).strip()
            continue
        package_match = re.match(r"(?:packageName|Package|package)\s*:\s*([A-Za-z0-9_.]+)", line)
        if package_match and PACKAGE_RE.fullmatch(package_match.group(1)):
            package = package_match.group(1)
            apps[package] = name or package
            name = ""
    if not apps:
        for package in PACKAGE_IN_TEXT_RE.findall(text or ""):
            if PACKAGE_RE.fullmatch(package) and package not in {"org.freedesktop.DBus", "waydroid.app.list"}:
                apps.setdefault(package, package)
    return apps


def list_waydroid_apps() -> dict[str, str]:
    ensure_session()
    result = run(["waydroid", "app", "list"], timeout=45)
    if result.returncode != 0:
        raise BridgeError((result.stderr or result.stdout or "Unable to list Waydroid apps").strip())
    return parse_app_list(result.stdout + "\n" + result.stderr)


def list_apps(*, include_all: bool = True) -> list[dict[str, Any]]:
    state = load_state()
    managed = state.get("apps", {}) if isinstance(state.get("apps"), dict) else {}
    installed = list_waydroid_apps()
    packages = set(installed) | set(managed)
    rows: list[dict[str, Any]] = []
    for package in sorted(packages, key=lambda item: (installed.get(item, managed.get(item, {}).get("name", item)).lower(), item)):
        record = managed.get(package, {}) if isinstance(managed.get(package), dict) else {}
        is_installed = package in installed
        if not include_all and not record:
            continue
        rows.append({
            "package": package,
            "name": record.get("name") or installed.get(package) or package,
            "installed": is_installed,
            "managed": bool(record),
            "profile": record.get("profile", "Desktop Balanced"),
            "fullscreen": bool(record.get("fullscreen", False)),
            "source_path": record.get("source_path", ""),
            "last_launched": int(record.get("last_launched") or 0),
            "native_abis": record.get("native_abis", []),
        })
    return rows


def get_prop(name: str) -> str:
    result = run(["waydroid", "prop", "get", name], timeout=25)
    if result.returncode != 0:
        return ""
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def set_prop(name: str, value: object) -> bool:
    wanted = str(value).lower() if isinstance(value, bool) else str(value)
    current = get_prop(name)
    if current.strip().lower() == wanted.strip().lower():
        return False
    result = run(["waydroid", "prop", "set", name, wanted], timeout=35)
    if result.returncode != 0:
        raise BridgeError((result.stderr or result.stdout or f"Unable to set {name}").strip())
    return True


def _csv_prop(name: str, package: str, enabled: bool) -> bool:
    package = validate_package(package)
    existing = [item.strip() for item in get_prop(name).split(",") if item.strip()]
    updated = [item for item in existing if item != package]
    if enabled:
        updated.append(package)
    # Waydroid documents a 91-character limit for these package lists.  Keep the
    # newest app and as many existing entries as safely fit.
    while len(",".join(updated)) > 91 and len(updated) > 1:
        updated.pop(0)
    return set_prop(name, ",".join(updated))


def apply_profile(
    package: str,
    profile_name: str,
    *,
    fullscreen: bool = False,
    fake_touch: bool | None = None,
    fake_wifi: bool | None = None,
    invert_colors: bool | None = None,
) -> dict[str, Any]:
    package = validate_package(package)
    if profile_name not in PROFILES:
        raise BridgeError(f"Unknown compatibility profile: {profile_name}")
    profile = PROFILES[profile_name]
    ensure_session()
    changed: list[str] = []

    def update(name: str, value: object) -> None:
        if set_prop(name, value):
            changed.append(name)

    update("persist.waydroid.multi_windows", False if fullscreen else profile.multi_window)
    update("persist.waydroid.width", "" if fullscreen else profile.width)
    update("persist.waydroid.height", "" if fullscreen else profile.height)
    update("persist.waydroid.width_padding", 0)
    update("persist.waydroid.height_padding", 0)
    update("persist.waydroid.suspend", not profile.keep_awake)
    update("persist.waydroid.no_presentation", profile.no_presentation)
    update("persist.waydroid.cursor_force_shm", profile.cursor_force_shm)
    # Clear the diagnostic override when leaving the black-screen profile so a
    # previous troubleshooting launch does not silently affect later apps.
    update(
        "persist.waydroid.use_subsurface",
        profile.use_subsurface if profile.use_subsurface is not None else "",
    )
    touch_enabled = profile.fake_touch if fake_touch is None else fake_touch
    wifi_enabled = profile.fake_wifi if fake_wifi is None else fake_wifi
    color_enabled = profile.invert_colors if invert_colors is None else invert_colors
    if _csv_prop("persist.waydroid.fake_touch", package, touch_enabled):
        changed.append("persist.waydroid.fake_touch")
    if _csv_prop("persist.waydroid.fake_wifi", package, wifi_enabled):
        changed.append("persist.waydroid.fake_wifi")
    update("persist.waydroid.invert_colors", color_enabled)

    if changed:
        stopped = run(["waydroid", "session", "stop"], timeout=40)
        if stopped.returncode != 0:
            raise BridgeError("Could not restart Android to apply the display mode. " + (stopped.stderr or stopped.stdout))
        time.sleep(1)
        ensure_session()
    return {"profile": asdict(profile), "changed_properties": changed}


def install_apk(apk_value: str | Path) -> dict[str, Any]:
    analysis = analyze_apk(apk_value)
    apk = Path(analysis["path"])
    ensure_session()
    state = load_state()
    known = str(state.get("apk_hashes", {}).get(analysis["sha256"], ""))
    before = list_waydroid_apps()
    result = run(["waydroid", "app", "install", apk], timeout=300)
    if result.returncode != 0:
        detail = (result.stderr + "\n" + result.stdout).strip()
        hint = ""
        if analysis["requires_arm_translation"] or any(word in detail.lower() for word in ("abi", "architecture", "no matching", "arm64")):
            hint = "\n\nThis APK appears to require ARM compatibility. Open Tools → ARM Compatibility, install libndk, and retry."
        raise BridgeError((detail or "Waydroid could not install the APK.") + hint)
    time.sleep(1)
    after = list_waydroid_apps()
    new_packages = sorted(set(after) - set(before))
    output_packages = [item for item in PACKAGE_IN_TEXT_RE.findall(result.stdout + "\n" + result.stderr) if PACKAGE_RE.fullmatch(item)]
    package = analysis["package"] or (new_packages[0] if len(new_packages) == 1 else "") or known
    if not package and len(output_packages) == 1:
        package = output_packages[0]
    if package:
        app_name = analysis["label"] or after.get(package) or apk.stem
        state.setdefault("apk_hashes", {})[analysis["sha256"]] = package
        previous = state.setdefault("apps", {}).get(package, {})
        state["apps"][package] = {
            **(previous if isinstance(previous, dict) else {}),
            "name": app_name,
            "source_path": str(apk),
            "sha256": analysis["sha256"],
            "native_abis": analysis["native_abis"],
            "version_name": analysis["version_name"],
            "version_code": analysis["version_code"],
            "profile": (previous or {}).get("profile", "Desktop Balanced") if isinstance(previous, dict) else "Desktop Balanced",
            "installed_at": int(time.time()),
        }
        save_state(state)
    return {
        "package": package,
        "new_packages": new_packages,
        "analysis": analysis,
        "output": (result.stdout + "\n" + result.stderr).strip(),
    }


def remember_package(apk_value: str | Path, package: str) -> dict[str, Any]:
    package = validate_package(package)
    analysis = analyze_apk(apk_value)
    state = load_state()
    state.setdefault("apk_hashes", {})[analysis["sha256"]] = package
    previous = state.setdefault("apps", {}).get(package, {})
    state["apps"][package] = {
        **(previous if isinstance(previous, dict) else {}),
        "name": analysis["label"] or Path(analysis["path"]).stem,
        "source_path": analysis["path"],
        "sha256": analysis["sha256"],
        "native_abis": analysis["native_abis"],
        "version_name": analysis["version_name"],
        "version_code": analysis["version_code"],
        "profile": (previous or {}).get("profile", "Desktop Balanced") if isinstance(previous, dict) else "Desktop Balanced",
        "installed_at": int(time.time()),
    }
    save_state(state)
    return {"package": package, "remembered": True}


def launch_package(
    package: str,
    profile_name: str = "Desktop Balanced",
    *,
    fake_touch: bool | None = None,
    fake_wifi: bool | None = None,
    invert_colors: bool | None = None,
    fullscreen: bool | None = None,
) -> dict[str, Any]:
    package = validate_package(package)
    if fullscreen is None:
        fullscreen = bool(load_state().get("apps", {}).get(package, {}).get("fullscreen", False))
    from fullscreen import configure_fullscreen
    configure_fullscreen(package, fullscreen)
    applied = apply_profile(
        package,
        profile_name,
        fullscreen=fullscreen,
        fake_touch=fake_touch,
        fake_wifi=fake_wifi,
        invert_colors=invert_colors,
    )
    result = run(["waydroid", "app", "launch", package], timeout=60)
    if result.returncode != 0:
        raise BridgeError((result.stderr or result.stdout or f"Unable to launch {package}").strip())
    state = load_state()
    record = state.setdefault("apps", {}).setdefault(package, {})
    record["fullscreen"] = fullscreen
    record["profile"] = profile_name
    record["last_launched"] = int(time.time())
    record["fake_touch"] = PROFILES[profile_name].fake_touch if fake_touch is None else fake_touch
    record["fake_wifi"] = PROFILES[profile_name].fake_wifi if fake_wifi is None else fake_wifi
    record["invert_colors"] = PROFILES[profile_name].invert_colors if invert_colors is None else invert_colors
    save_state(state)
    return {"launched": package, **applied}


def set_fullscreen(package: str, enabled: bool) -> dict[str, Any]:
    package = validate_package(package)
    record = load_state().get("apps", {}).get(package, {})
    # Use the same display path as launch, preserving this app's compatibility options.
    return launch_package(
        package, record.get("profile", "Desktop Balanced"), fullscreen=enabled,
        fake_touch=record.get("fake_touch"), fake_wifi=record.get("fake_wifi"),
        invert_colors=record.get("invert_colors"),
    )


def remove_package(package: str, *, remove_record: bool = False) -> dict[str, Any]:
    package = validate_package(package)
    ensure_session()
    result = run(["waydroid", "app", "remove", package], timeout=90)
    if result.returncode != 0:
        raise BridgeError((result.stderr or result.stdout or f"Unable to remove {package}").strip())
    state = load_state()
    if remove_record:
        state.setdefault("apps", {}).pop(package, None)
        hashes = state.setdefault("apk_hashes", {})
        for key, value in list(hashes.items()):
            if value == package:
                hashes.pop(key, None)
        save_state(state)
    return {"removed": package, "record_removed": remove_record}


def _desktop_value(value: str) -> str:
    return " ".join(str(value or "").replace("\n", " ").replace("\r", " ").split())


def _shortcut_icon(package: str) -> str:
    candidates = list(SHORTCUT_DIR.glob(f"*{package}*.desktop"))
    for candidate in candidates:
        if candidate.name.startswith("apkbridge-"):
            continue
        try:
            for line in candidate.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("Icon=") and line[5:].strip():
                    return line[5:].strip()
        except OSError:
            continue
    return "apkbridge"


def create_shortcut(package: str, name: str = "", profile_name: str = "Desktop Balanced") -> dict[str, str]:
    package = validate_package(package)
    if profile_name not in PROFILES:
        raise BridgeError(f"Unknown compatibility profile: {profile_name}")
    state = load_state()
    record = state.get("apps", {}).get(package, {})
    app_name = _desktop_value(name or (record.get("name") if isinstance(record, dict) else "") or package)
    launcher = Path.home() / ".local" / "bin" / "apkbridge"
    launcher_text = str(launcher).replace("\\", "\\\\").replace('"', '\\"')
    safe_profile = profile_name.replace('"', "")
    exec_line = f'"{launcher_text}" --launch {package} --profile "{safe_profile}"'
    desktop = SHORTCUT_DIR / f"apkbridge-{package}.desktop"
    content = "\n".join([
        "[Desktop Entry]",
        "Type=Application",
        f"Name={app_name}",
        f"Comment=Run {app_name} through APKBridge",
        f"Exec={exec_line}",
        f"Icon={_shortcut_icon(package)}",
        "Terminal=false",
        "Categories=Utility;Game;",
        "StartupNotify=true",
        "X-APKBridge-Package=" + package,
        "",
    ])
    desktop.write_text(content, encoding="utf-8")
    desktop.chmod(0o644)
    if which("desktop-file-validate"):
        run(["desktop-file-validate", desktop], timeout=20)
    if which("update-desktop-database"):
        run(["update-desktop-database", SHORTCUT_DIR], timeout=30)
    return {"shortcut": str(desktop), "package": package}


def setup_waydroid() -> dict[str, Any]:
    if os.geteuid() != 0:
        raise BridgeError("Waydroid setup requires administrator approval.")
    if which("waydroid"):
        return {"installed": True, "already_installed": True, "reboot_required": False}
    if which("rpm-ostree"):
        result = run(["rpm-ostree", "install", "waydroid"], timeout=1200)
        if result.returncode != 0:
            raise BridgeError((result.stderr or result.stdout or "rpm-ostree could not install Waydroid").strip())
        return {"installed": True, "already_installed": False, "reboot_required": True}
    if which("dnf"):
        result = run(["dnf", "install", "-y", "waydroid"], timeout=1200)
    elif which("apt-get"):
        run(["apt-get", "update"], timeout=1200, check=True)
        result = run(["apt-get", "install", "-y", "waydroid"], timeout=1200)
    elif which("pacman"):
        result = run(["pacman", "-S", "--needed", "--noconfirm", "waydroid"], timeout=1200)
    else:
        raise BridgeError("This distribution needs Waydroid installed manually. See the APKBridge setup guide.")
    if result.returncode != 0:
        raise BridgeError((result.stderr or result.stdout or "The package manager could not install Waydroid").strip())
    return {"installed": True, "already_installed": False, "reboot_required": False}


def initialize_waydroid() -> dict[str, Any]:
    if os.geteuid() != 0:
        raise BridgeError("Waydroid initialization requires administrator approval.")
    if not which("waydroid"):
        raise BridgeError("Install Waydroid before initializing it.")
    if waydroid_initialized():
        return {"initialized": True, "already_initialized": True}
    result = run(["waydroid", "init"], timeout=1800)
    if result.returncode != 0:
        raise BridgeError((result.stderr or result.stdout or "Waydroid initialization failed").strip())
    return {"initialized": True, "already_initialized": False}


def diagnostic_report(package: str = "") -> dict[str, str]:
    if package:
        package = validate_package(package)
    _ensure_dirs()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    report = LOG_DIR / f"diagnostic-{stamp}.txt"
    sections: list[tuple[str, str]] = []
    sections.append(("APKBridge", json.dumps({"version": VERSION, "status": status()}, indent=2)))
    sections.append(("Managed state", json.dumps(load_state(), indent=2)))

    commands: list[tuple[str, list[str], int]] = []
    if which("waydroid"):
        commands.extend([
            ("Waydroid status", ["waydroid", "status"], 30),
            ("Waydroid version", ["waydroid", "--version"], 30),
            ("Waydroid recent log", ["waydroid", "log", "-n", "180"], 45),
        ])
        if package:
            commands.append(("Android package details", ["waydroid", "shell", "dumpsys", "package", package], 60))
    for title, command, timeout in commands:
        try:
            result = run(command, timeout=timeout)
            text = (result.stdout + "\n" + result.stderr).strip()
            sections.append((title, text[-30000:] if text else "(no output)"))
        except BridgeError as exc:
            sections.append((title, f"Unable to collect: {exc}"))
    body = ["APKBridge diagnostic report", f"Created: {time.strftime('%Y-%m-%d %H:%M:%S')}", ""]
    for title, text in sections:
        body.extend([f"===== {title} =====", text, ""])
    report.write_text("\n".join(body), encoding="utf-8")
    return {"report": str(report)}


def profiles_payload() -> dict[str, dict[str, Any]]:
    return {name: asdict(profile) for name, profile in PROFILES.items()}


def _emit(payload: dict[str, Any]) -> None:
    print("APKBRIDGE_JSON=" + json.dumps(payload), flush=True)


def _bool_or_none(value: str) -> bool | None:
    if value == "default":
        return None
    return value == "on"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="APKBridge Waydroid backend")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("profiles")
    sub.add_parser("start")
    sub.add_parser("stop")
    analyze = sub.add_parser("analyze")
    analyze.add_argument("apk")
    install = sub.add_parser("install")
    install.add_argument("apk")
    remember = sub.add_parser("remember")
    remember.add_argument("apk")
    remember.add_argument("package")
    listing = sub.add_parser("list")
    listing.add_argument("--managed-only", action="store_true")
    launch = sub.add_parser("launch")
    launch.add_argument("package")
    launch.add_argument("--profile", choices=list(PROFILES), default="Desktop Balanced")
    launch.add_argument("--fullscreen", choices=("default", "on", "off"), default="default")
    launch.add_argument("--fake-touch", choices=("default", "on", "off"), default="default")
    launch.add_argument("--fake-wifi", choices=("default", "on", "off"), default="default")
    launch.add_argument("--invert-colors", choices=("default", "on", "off"), default="default")
    display = sub.add_parser("fullscreen")
    display.add_argument("package")
    display.add_argument("mode", choices=("on", "off"))
    remove = sub.add_parser("remove")
    remove.add_argument("package")
    remove.add_argument("--forget", action="store_true")
    shortcut = sub.add_parser("shortcut")
    shortcut.add_argument("package")
    shortcut.add_argument("--name", default="")
    shortcut.add_argument("--profile", choices=list(PROFILES), default="Desktop Balanced")
    diagnose = sub.add_parser("diagnose")
    diagnose.add_argument("package", nargs="?", default="")
    sub.add_parser("setup-waydroid")
    sub.add_parser("initialize-waydroid")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "status":
            payload = status()
        elif args.command == "profiles":
            payload = {"profiles": profiles_payload()}
        elif args.command == "start":
            ensure_session()
            payload = {"started": True}
        elif args.command == "stop":
            payload = stop_session()
        elif args.command == "analyze":
            payload = analyze_apk(args.apk)
        elif args.command == "install":
            payload = install_apk(args.apk)
        elif args.command == "remember":
            payload = remember_package(args.apk, args.package)
        elif args.command == "list":
            payload = {"apps": list_apps(include_all=not args.managed_only)}
        elif args.command == "launch":
            payload = launch_package(
                args.package,
                args.profile,
                fullscreen=_bool_or_none(args.fullscreen),
                fake_touch=_bool_or_none(args.fake_touch),
                fake_wifi=_bool_or_none(args.fake_wifi),
                invert_colors=_bool_or_none(args.invert_colors),
            )
        elif args.command == "fullscreen":
            payload = set_fullscreen(args.package, args.mode == "on")
        elif args.command == "remove":
            payload = remove_package(args.package, remove_record=args.forget)
        elif args.command == "shortcut":
            payload = create_shortcut(args.package, args.name, args.profile)
        elif args.command == "diagnose":
            payload = diagnostic_report(args.package)
        elif args.command == "setup-waydroid":
            payload = setup_waydroid()
        elif args.command == "initialize-waydroid":
            payload = initialize_waydroid()
        else:
            raise BridgeError("Unknown APKBridge operation")
        _emit(payload)
        return 0
    except Exception as exc:  # noqa: BLE001  # CLI boundary: always return a useful UI error.
        log("ERROR: " + str(exc))
        print("APKBRIDGE_ERROR=" + str(exc), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
