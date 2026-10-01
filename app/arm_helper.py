#!/usr/bin/env python3
"""Privileged, opt-in ARM translation manager for APKBridge.

The translation files are not bundled with APKBridge.  With explicit user
approval this helper obtains the community Waydroid Extras Script, records the
exact Git revision, snapshots Waydroid's configuration, and asks that script to
install or remove libndk/libhoudini.
"""

from __future__ import annotations

import argparse
import configparser
import json
import os
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path

REPOSITORY = "https://github.com/casualsnek/waydroid_script.git"
CACHE = Path("/var/cache/apkbridge/waydroid_script")
BACKUPS = Path("/var/lib/apkbridge/arm-backups")
STATE = Path("/var/lib/apkbridge/arm-state.json")
LOG = Path("/var/log/apkbridge-arm.log")


class ArmError(RuntimeError):
    pass


def log(message: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(line, flush=True)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def run(command: list[object], *, timeout: int = 600, check: bool = False) -> subprocess.CompletedProcess[str]:
    cmd = [str(item) for item in command]
    log("$ " + " ".join(cmd))
    try:
        result = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ArmError(str(exc)) from exc
    if result.stdout.strip():
        log(result.stdout.strip())
    if result.stderr.strip():
        log(result.stderr.strip())
    if check and result.returncode != 0:
        raise ArmError((result.stderr or result.stdout or "command failed").strip())
    return result


def require_root() -> None:
    if os.geteuid() != 0:
        raise ArmError("ARM compatibility changes require administrator approval.")


def current_bridge() -> str:
    config = Path("/var/lib/waydroid/waydroid.cfg")
    try:
        parser = configparser.ConfigParser()
        parser.read(config)
        bridge = parser.get("properties", "ro.dalvik.vm.native.bridge", fallback="").lower()
        if "libndk" in bridge:
            return "libndk"
        if "houdini" in bridge:
            return "libhoudini"
    except (OSError, configparser.Error):
        pass
    return "none"


def cpu_info() -> dict[str, object]:
    flags: set[str] = set()
    model = platform.processor() or "unknown"
    try:
        text = Path("/proc/cpuinfo").read_text(errors="ignore")
        match = re.search(r"^model name\s*:\s*(.+)$", text, re.MULTILINE)
        if match:
            model = match.group(1).strip()
        match = re.search(r"^flags\s*:\s*(.+)$", text, re.MULTILINE)
        if match:
            flags = set(match.group(1).split())
    except OSError:
        pass
    return {"architecture": platform.machine(), "model": model, "sse4_2": "sse4_2" in flags}


def snapshot() -> Path:
    require_root()
    destination = BACKUPS / time.strftime("%Y%m%d-%H%M%S")
    destination.mkdir(parents=True, exist_ok=True)
    for source in (
        Path("/var/lib/waydroid/waydroid.cfg"),
        Path("/var/lib/waydroid/waydroid.prop"),
        Path("/var/lib/waydroid/waydroid_base.prop"),
    ):
        if source.is_file():
            shutil.copy2(source, destination / source.name)
    metadata = {"created": int(time.time()), "native_bridge": current_bridge()}
    (destination / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return destination


def install_dependencies() -> dict[str, object]:
    required = [name for name in ("git", "lzip", "python3") if not shutil.which(name)]
    if not required:
        return {"reboot_required": False}
    if shutil.which("rpm-ostree"):
        packages = ["git", "lzip", "python3"]
        result = run(["rpm-ostree", "install", *packages], timeout=1200)
        if result.returncode != 0:
            raise ArmError((result.stderr or result.stdout or "Unable to layer ARM helper dependencies").strip())
        return {"reboot_required": True}
    if shutil.which("dnf"):
        run(["dnf", "install", "-y", "git", "lzip", "python3", "python3-pip"], timeout=1200, check=True)
    elif shutil.which("apt-get"):
        run(["apt-get", "update"], timeout=1200, check=True)
        run(["apt-get", "install", "-y", "git", "lzip", "python3", "python3-pip", "python3-venv"], timeout=1200, check=True)
    elif shutil.which("pacman"):
        run(["pacman", "-S", "--needed", "--noconfirm", "git", "lzip", "python", "python-pip"], timeout=1200, check=True)
    else:
        raise ArmError("Install git, lzip, Python, pip, and Python venv support, then retry.")
    return {"reboot_required": False}


def prepare_script() -> tuple[Path, str]:
    dependency_result = install_dependencies()
    if dependency_result.get("reboot_required"):
        raise ArmError("ARM helper dependencies were layered. Reboot the computer, then run this action again.")
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    if (CACHE / ".git").is_dir():
        run(["git", "-C", CACHE, "fetch", "--depth=1", "origin", "main"], timeout=240, check=True)
        run(["git", "-C", CACHE, "reset", "--hard", "origin/main"], timeout=90, check=True)
    else:
        if CACHE.exists():
            shutil.rmtree(CACHE)
        run(["git", "clone", "--depth=1", REPOSITORY, CACHE], timeout=300, check=True)
    revision_result = run(["git", "-C", CACHE, "rev-parse", "HEAD"], timeout=30, check=True)
    revision = revision_result.stdout.strip()
    venv = CACHE / ".venv"
    python = venv / "bin" / "python3"
    if not python.is_file():
        run(["python3", "-m", "venv", venv], timeout=180, check=True)
    run([python, "-m", "pip", "install", "--disable-pip-version-check", "-r", CACHE / "requirements.txt"], timeout=600, check=True)
    return python, revision


def invoke(action: str, translator: str) -> tuple[subprocess.CompletedProcess[str], str]:
    python, revision = prepare_script()
    result = run([python, CACHE / "main.py", action, translator], timeout=1200)
    return result, revision


def install(translator: str) -> dict[str, object]:
    require_root()
    if translator not in {"libndk", "libhoudini"}:
        raise ArmError("Unknown ARM translator")
    backup = snapshot()
    other = "libhoudini" if translator == "libndk" else "libndk"
    # Never leave both native bridges deliberately installed.
    try:
        invoke("uninstall", other)
    except ArmError as exc:
        log(f"Opposite translator removal was non-fatal: {exc}")
    result, revision = invoke("install", translator)
    if result.returncode != 0:
        raise ArmError((result.stderr or result.stdout or f"Unable to install {translator}").strip())
    data = {
        "translator": translator,
        "installed_at": int(time.time()),
        "source": REPOSITORY,
        "source_revision": revision,
        "snapshot": str(backup),
        "cpu": cpu_info(),
    }
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def remove(translator: str) -> dict[str, object]:
    require_root()
    if translator not in {"libndk", "libhoudini"}:
        raise ArmError("Unknown ARM translator")
    result, revision = invoke("uninstall", translator)
    if result.returncode != 0:
        raise ArmError((result.stderr or result.stdout or f"Unable to remove {translator}").strip())
    return {"removed": translator, "source_revision": revision}


def status() -> dict[str, object]:
    saved: dict[str, object] = {}
    try:
        value = json.loads(STATE.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            saved = value
    except (OSError, ValueError):
        pass
    return {"native_bridge": current_bridge(), "cpu": cpu_info(), "saved_state": saved}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="APKBridge ARM compatibility helper")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    install_parser = sub.add_parser("install")
    install_parser.add_argument("translator", choices=("libndk", "libhoudini"), default="libndk", nargs="?")
    remove_parser = sub.add_parser("remove")
    remove_parser.add_argument("translator", choices=("libndk", "libhoudini"), default="libndk", nargs="?")
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            payload = status()
        elif args.command == "install":
            payload = install(args.translator)
        else:
            payload = remove(args.translator)
        print("APKBRIDGE_JSON=" + json.dumps(payload), flush=True)
        return 0
    except Exception as exc:  # noqa: BLE001  # Privileged CLI boundary for UI-visible errors.
        log("ERROR: " + str(exc))
        print("APKBRIDGE_ERROR=" + str(exc), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
