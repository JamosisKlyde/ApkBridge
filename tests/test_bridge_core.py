# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 JamosisKlyde and APKBridge contributors
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "bridge_core.py"
SPEC = importlib.util.spec_from_file_location("bridge_core_under_test", MODULE_PATH)
assert SPEC and SPEC.loader
core = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = core
SPEC.loader.exec_module(core)


class ParseAppListTests(unittest.TestCase):
    def test_parses_waydroid_blocks(self) -> None:
        text = """
        Name: Calculator
        packageName: com.android.calculator2
        categories:
        Name: Example TV
        packageName: com.example.tv
        """
        self.assertEqual(
            core.parse_app_list(text),
            {
                "com.android.calculator2": "Calculator",
                "com.example.tv": "Example TV",
            },
        )

    def test_falls_back_to_package_shaped_identifiers(self) -> None:
        apps = core.parse_app_list("installed com.example.one and com.example.two")
        self.assertEqual(apps["com.example.one"], "com.example.one")
        self.assertEqual(apps["com.example.two"], "com.example.two")


class ApkAnalysisTests(unittest.TestCase):
    def make_apk(self, root: Path, members: list[str]) -> Path:
        path = root / "sample.apk"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("AndroidManifest.xml", b"placeholder")
            for member in members:
                archive.writestr(member, b"native-library")
        return path

    def test_detects_arm_only_apk_on_x86_64(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            apk = self.make_apk(Path(folder), ["lib/arm64-v8a/libgame.so"])
            with mock.patch.object(core.platform, "machine", return_value="x86_64"), mock.patch.object(core, "package_from_aapt", return_value={"package": "", "version_code": "", "version_name": "", "min_sdk": "", "label": ""}):
                result = core.analyze_apk(apk)
            self.assertTrue(result["requires_arm_translation"])
            self.assertEqual(result["native_abis"], ["arm64-v8a"])
            self.assertEqual(len(result["sha256"]), 64)

    def test_accepts_x86_64_native_apk(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            apk = self.make_apk(Path(folder), ["lib/x86_64/libgame.so"])
            with mock.patch.object(core.platform, "machine", return_value="x86_64"), mock.patch.object(core, "package_from_aapt", return_value={"package": "", "version_code": "", "version_name": "", "min_sdk": "", "label": ""}):
                result = core.analyze_apk(apk)
            self.assertFalse(result["requires_arm_translation"])
            self.assertFalse(result["incompatible_native_architecture"])

    def test_rejects_non_apk_bundle_for_preview(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bundle.xapk"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("base.apk", b"not-needed")
            with self.assertRaises(core.BridgeError):
                core.analyze_apk(path)


class ValidationTests(unittest.TestCase):
    def test_package_validation(self) -> None:
        self.assertEqual(core.validate_package("com.example.app"), "com.example.app")
        for bad in ("", "example", "com.example;rm", "com example.app"):
            with self.subTest(bad=bad), self.assertRaises(core.BridgeError):
                core.validate_package(bad)

    def test_all_profiles_have_sane_dimensions(self) -> None:
        self.assertGreaterEqual(len(core.PROFILES), 6)
        for profile in core.PROFILES.values():
            self.assertGreaterEqual(profile.width, 480)
            self.assertGreaterEqual(profile.height, 480)


class ShortcutTests(unittest.TestCase):
    def test_shortcut_uses_validated_package_and_saved_profile(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            state_file = root / "state.json"
            shortcut_dir = root / "applications"
            shortcut_dir.mkdir()
            with mock.patch.object(core, "APPDATA", root), mock.patch.object(core, "LOG_DIR", root / "logs"), mock.patch.object(core, "CORE_LOG", root / "logs" / "log.txt"), mock.patch.object(core, "STATE_FILE", state_file), mock.patch.object(core, "SHORTCUT_DIR", shortcut_dir), mock.patch.object(core, "which", return_value=""):
                core.save_state({"schema": 1, "apps": {"com.example.app": {"name": "Example"}}, "apk_hashes": {}})
                result = core.create_shortcut("com.example.app", "Example", "Gaming")
            text = Path(result["shortcut"]).read_text(encoding="utf-8")
            self.assertIn("--launch com.example.app", text)
            self.assertIn('--profile "Gaming"', text)
            self.assertIn("Name=Example", text)


if __name__ == "__main__":
    unittest.main()
