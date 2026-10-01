#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 JamosisKlyde and APKBridge contributors
"""APKBridge graphical desktop application."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from bridge_core import PROFILES, VERSION, BridgeError, launch_package
from PyQt6.QtCore import QProcess, Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices, QFont, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

CORE = Path(__file__).with_name("bridge_core.py")
ARM_HELPER = Path(__file__).with_name("arm_helper.py")
ICON = Path(__file__).with_name("apkbridge.svg")
APPDATA = Path.home() / ".local" / "share" / "apkbridge"
CONFIG_FILE = APPDATA / "config.json"
LOG_DIR = APPDATA / "logs"


APP_STYLE = """
QMainWindow, QWidget { background: #15131a; color: #f6f1f5; }
QTabWidget::pane { border: 1px solid #3a303c; border-radius: 8px; background: #1c1820; }
QTabBar::tab { background: #27212b; color: #d6cbd5; padding: 10px 18px; margin-right: 2px; }
QTabBar::tab:selected { background: #bd2c69; color: white; }
QGroupBox { border: 1px solid #403542; border-radius: 9px; margin-top: 12px; padding: 14px 10px 10px 10px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #ff87ba; }
QLineEdit, QComboBox, QPlainTextEdit, QListWidget { background: #211c25; border: 1px solid #4d4050; border-radius: 6px; padding: 7px; color: #fff; selection-background-color: #bd2c69; }
QComboBox QAbstractItemView { background: #211c25; color: white; selection-background-color: #bd2c69; }
QPushButton { background: #352c39; border: 1px solid #5b4a5f; border-radius: 7px; padding: 8px 12px; color: white; }
QPushButton:hover { background: #49384a; border-color: #ff6aaa; }
QPushButton:pressed { background: #2a222d; }
QPushButton:disabled { color: #756c76; background: #242026; border-color: #373039; }
QPushButton#primary { background: #c52d6d; border-color: #e14c8a; font-weight: 700; padding: 10px 16px; }
QPushButton#primary:hover { background: #de397b; }
QPushButton#safe { background: #31633f; border-color: #4d9562; }
QLabel#muted { color: #b8aeb9; }
QLabel#statusGood { color: #75dc91; font-weight: 600; }
QLabel#statusWarn { color: #ffc168; font-weight: 600; }
QLabel#statusBad { color: #ff7f8f; font-weight: 600; }
QProgressBar { border: 1px solid #4d4050; border-radius: 5px; background: #211c25; text-align: center; }
QProgressBar::chunk { background: #c52d6d; }
QCheckBox { spacing: 8px; }
QScrollArea { border: none; }
"""


def load_config() -> dict[str, Any]:
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(data: dict[str, Any]) -> None:
    APPDATA.mkdir(parents=True, exist_ok=True)
    temporary = CONFIG_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temporary.replace(CONFIG_FILE)


def human_size(value: int) -> str:
    size = float(value)
    for suffix in ("B", "KiB", "MiB", "GiB"):
        if size < 1024 or suffix == "GiB":
            return f"{size:.1f} {suffix}" if suffix != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} GiB"


def parse_payload(output: str) -> tuple[dict[str, Any] | None, str]:
    payload = None
    error = ""
    for line in output.splitlines():
        if line.startswith("APKBRIDGE_JSON="):
            try:
                value = json.loads(line.split("=", 1)[1])
                if isinstance(value, dict):
                    payload = value
            except ValueError:
                pass
        elif line.startswith("APKBRIDGE_ERROR="):
            error = line.split("=", 1)[1].strip()
    return payload, error


class MainWindow(QMainWindow):
    def __init__(self, initial_apk: str = "") -> None:
        super().__init__()
        self.setWindowTitle(f"APKBridge {VERSION}")
        self.resize(1080, 780)
        self.setMinimumSize(860, 650)
        if ICON.is_file():
            self.setWindowIcon(QIcon(str(ICON)))
        self.setAcceptDrops(True)
        self.config = load_config()
        self.process: QProcess | None = None
        self.task_name = ""
        self.task_output = ""
        self.task_callback: Callable[[dict[str, Any]], None] | None = None
        self.task_error_callback: Callable[[str], None] | None = None
        self.quiet_task = False
        self.last_status: dict[str, Any] = {}
        self.last_analysis: dict[str, Any] = {}
        self.current_apps: list[dict[str, Any]] = []
        self._build_ui()
        self._restore_config(initial_apk)
        QTimer.singleShot(100, self.refresh_status)
        if self.apk_edit.text():
            QTimer.singleShot(350, self.analyze_selected_apk)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(12)

        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title = QLabel("APKBridge")
        title_font = QFont()
        title_font.setPointSize(22)
        title_font.setBold(True)
        title.setFont(title_font)
        subtitle = QLabel("Run Android APKs as desktop applications through Waydroid")
        subtitle.setObjectName("muted")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header.addLayout(title_col)
        header.addStretch(1)
        self.header_status = QLabel("Checking Waydroid…")
        self.header_status.setObjectName("statusWarn")
        header.addWidget(self.header_status)
        outer.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_run_tab(), "Run APK")
        self.tabs.addTab(self._build_library_tab(), "Android Apps")
        self.tabs.addTab(self._build_tools_tab(), "Setup && Repair")
        self.tabs.addTab(self._build_log_tab(), "Activity Log")
        self.tabs.currentChanged.connect(self._tab_changed)
        outer.addWidget(self.tabs, 1)

        footer = QHBoxLayout()
        self.footer_status = QLabel("Ready")
        self.footer_status.setObjectName("muted")
        footer.addWidget(self.footer_status, 1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedWidth(170)
        self.progress.hide()
        footer.addWidget(self.progress)
        outer.addLayout(footer)

    def _scroll_page(self) -> tuple[QScrollArea, QVBoxLayout]:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        scroll.setWidget(page)
        return scroll, layout

    def _build_run_tab(self) -> QWidget:
        scroll, layout = self._scroll_page()

        status_box = QGroupBox("System readiness")
        status_grid = QGridLayout(status_box)
        self.distro_value = QLabel("—")
        self.waydroid_value = QLabel("—")
        self.session_value = QLabel("—")
        self.arm_value = QLabel("—")
        status_grid.addWidget(QLabel("Linux:"), 0, 0)
        status_grid.addWidget(self.distro_value, 0, 1)
        status_grid.addWidget(QLabel("Waydroid:"), 0, 2)
        status_grid.addWidget(self.waydroid_value, 0, 3)
        status_grid.addWidget(QLabel("Session:"), 1, 0)
        status_grid.addWidget(self.session_value, 1, 1)
        status_grid.addWidget(QLabel("ARM translation:"), 1, 2)
        status_grid.addWidget(self.arm_value, 1, 3)
        refresh = QPushButton("Recheck")
        refresh.clicked.connect(self.refresh_status)
        status_grid.addWidget(refresh, 0, 4, 2, 1)
        layout.addWidget(status_box)

        select_box = QGroupBox("Android package")
        select_grid = QGridLayout(select_box)
        self.apk_edit = QLineEdit()
        self.apk_edit.setPlaceholderText("Choose an Android .apk file or drag it into this window")
        self.apk_edit.editingFinished.connect(self._apk_edited)
        browse = QPushButton("Browse APK…")
        browse.clicked.connect(self.browse_apk)
        analyze = QPushButton("Inspect")
        analyze.clicked.connect(self.analyze_selected_apk)
        select_grid.addWidget(self.apk_edit, 0, 0)
        select_grid.addWidget(browse, 0, 1)
        select_grid.addWidget(analyze, 0, 2)
        self.analysis_label = QLabel("No APK selected. APKBridge will check file integrity and native CPU support before installation.")
        self.analysis_label.setWordWrap(True)
        self.analysis_label.setObjectName("muted")
        select_grid.addWidget(self.analysis_label, 1, 0, 1, 3)
        layout.addWidget(select_box)

        launch_box = QGroupBox("Launch profile")
        launch_grid = QGridLayout(launch_box)
        self.profile_combo = QComboBox()
        self.profile_combo.addItems(list(PROFILES))
        self.profile_combo.currentTextChanged.connect(self._profile_changed)
        self.profile_description = QLabel()
        self.profile_description.setWordWrap(True)
        self.profile_description.setObjectName("muted")
        launch_grid.addWidget(QLabel("Profile:"), 0, 0)
        launch_grid.addWidget(self.profile_combo, 0, 1, 1, 3)
        launch_grid.addWidget(self.profile_description, 1, 1, 1, 3)
        self.fake_touch = QCheckBox("Treat mouse clicks as touch")
        self.fake_wifi = QCheckBox("Report a Wi-Fi connection to this app")
        self.invert_colors = QCheckBox("Invert RGBA/BGRA channels (color troubleshooting)")
        launch_grid.addWidget(self.fake_touch, 2, 1)
        launch_grid.addWidget(self.fake_wifi, 2, 2)
        launch_grid.addWidget(self.invert_colors, 3, 1, 1, 2)
        self.package_edit = QLineEdit()
        self.package_edit.setPlaceholderText("Detected after installation, e.g. com.example.app")
        self.fullscreen = QCheckBox("Launch fullscreen (restarts Android when needed)")
        self.fullscreen.setToolTip("Uses a full Android display. Changing display mode restarts Android and closes running apps.")
        launch_grid.addWidget(self.fullscreen, 5, 1, 1, 3)
        launch_grid.addWidget(QLabel("Package name:"), 4, 0)
        launch_grid.addWidget(self.package_edit, 4, 1, 1, 3)
        layout.addWidget(launch_box)

        buttons = QHBoxLayout()
        self.install_launch_btn = QPushButton("Install && Launch")
        self.install_launch_btn.setObjectName("primary")
        self.install_launch_btn.clicked.connect(lambda: self.install_apk(launch_after=True))
        install_only = QPushButton("Install Only")
        install_only.clicked.connect(lambda: self.install_apk(launch_after=False))
        launch_existing = QPushButton("Launch Installed App")
        launch_existing.clicked.connect(self.launch_current)
        shortcut = QPushButton("Create App Shortcut")
        shortcut.clicked.connect(self.create_current_shortcut)
        buttons.addWidget(self.install_launch_btn)
        buttons.addWidget(install_only)
        buttons.addWidget(launch_existing)
        buttons.addWidget(shortcut)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        display_box = QGroupBox("Running Android window")
        display_layout = QVBoxLayout(display_box)
        display_buttons = QHBoxLayout()
        self.enter_fullscreen_btn = QPushButton("Enter Fullscreen")
        self.exit_fullscreen_btn = QPushButton("Exit Fullscreen")
        self.enter_fullscreen_btn.clicked.connect(lambda: self.set_current_fullscreen(True))
        self.exit_fullscreen_btn.clicked.connect(lambda: self.set_current_fullscreen(False))
        display_buttons.addWidget(self.enter_fullscreen_btn)
        display_buttons.addWidget(self.exit_fullscreen_btn)
        display_buttons.addStretch(1)
        display_layout.addLayout(display_buttons)
        display_note = QLabel("Switches Android display mode and relaunches the selected app. Other Android apps may close. "
                              "Alt+Tab back here to exit fullscreen. Requires KDE Plasma.")
        display_note.setWordWrap(True)
        display_note.setObjectName("muted")
        display_layout.addWidget(display_note)
        layout.addWidget(display_box)

        reality = QLabel(
            "APKBridge runs apps inside Waydroid. ARM-only apps may need the optional libndk translator; "
            "DRM, anti-cheat, SafetyNet/Play Integrity, and hardware-specific apps may still refuse to run."
        )
        reality.setWordWrap(True)
        reality.setObjectName("muted")
        layout.addWidget(reality)
        layout.addStretch(1)
        return scroll

    def _build_library_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        top = QHBoxLayout()
        label = QLabel("Apps APKBridge has imported, plus other apps currently visible to Waydroid")
        label.setObjectName("muted")
        top.addWidget(label, 1)
        self.managed_only = QCheckBox("APKBridge apps only")
        self.managed_only.setChecked(True)
        self.managed_only.toggled.connect(self.refresh_apps)
        top.addWidget(self.managed_only)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_apps)
        top.addWidget(refresh)
        layout.addLayout(top)

        self.app_list = QListWidget()
        self.app_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.app_list.currentItemChanged.connect(self._app_selected)
        self.app_list.itemDoubleClicked.connect(lambda _item: self.launch_library_app())
        layout.addWidget(self.app_list, 1)
        self.app_detail = QLabel("Select an app to see its package and saved launch profile.")
        self.app_detail.setWordWrap(True)
        self.app_detail.setObjectName("muted")
        layout.addWidget(self.app_detail)

        actions = QHBoxLayout()
        launch = QPushButton("Launch")
        launch.setObjectName("primary")
        launch.clicked.connect(self.launch_library_app)
        shortcut = QPushButton("Create Shortcut")
        shortcut.clicked.connect(self.create_library_shortcut)
        diagnose = QPushButton("Build Diagnostic Report")
        diagnose.clicked.connect(self.diagnose_library_app)
        remove = QPushButton("Uninstall from Waydroid")
        remove.clicked.connect(self.remove_library_app)
        actions.addWidget(launch)
        actions.addWidget(shortcut)
        actions.addWidget(diagnose)
        actions.addStretch(1)
        actions.addWidget(remove)
        layout.addLayout(actions)
        return page

    def _build_tools_tab(self) -> QWidget:
        scroll, layout = self._scroll_page()

        setup = QGroupBox("Waydroid setup")
        setup_layout = QVBoxLayout(setup)
        setup_note = QLabel(
            "Fedora is supported directly. Bazzite/Kinoite/Silverblue can layer Waydroid with rpm-ostree and will require a reboot. "
            "Wayland is required for normal desktop integration."
        )
        setup_note.setWordWrap(True)
        setup_note.setObjectName("muted")
        setup_layout.addWidget(setup_note)
        setup_buttons = QHBoxLayout()
        install = QPushButton("Install Waydroid")
        install.clicked.connect(self.install_waydroid)
        initialize = QPushButton("Initialize Android Image")
        initialize.clicked.connect(self.initialize_waydroid)
        start = QPushButton("Start Session")
        start.setObjectName("safe")
        start.clicked.connect(self.start_session)
        stop = QPushButton("Stop Session")
        stop.clicked.connect(self.stop_session)
        full = QPushButton("Open Full Android UI")
        full.clicked.connect(self.open_full_ui)
        for button in (install, initialize, start, stop, full):
            setup_buttons.addWidget(button)
        setup_buttons.addStretch(1)
        setup_layout.addLayout(setup_buttons)
        layout.addWidget(setup)

        arm = QGroupBox("ARM compatibility — optional")
        arm_layout = QVBoxLayout(arm)
        arm_note = QLabel(
            "Many phone APKs contain ARM code while Fedora PCs use x86-64. The recommended libndk translator performs compatibility translation. "
            "This changes Waydroid's system image, creates a configuration snapshot first, and is never installed automatically."
        )
        arm_note.setWordWrap(True)
        arm_note.setObjectName("muted")
        arm_layout.addWidget(arm_note)
        arm_buttons = QHBoxLayout()
        install_ndk = QPushButton("Install / Repair libndk")
        install_ndk.clicked.connect(self.install_arm)
        remove_ndk = QPushButton("Remove libndk")
        remove_ndk.clicked.connect(self.remove_arm)
        arm_buttons.addWidget(install_ndk)
        arm_buttons.addWidget(remove_ndk)
        arm_buttons.addStretch(1)
        arm_layout.addLayout(arm_buttons)
        layout.addWidget(arm)

        repair = QGroupBox("Logs and repair information")
        repair_layout = QVBoxLayout(repair)
        repair_note = QLabel(
            "A diagnostic report contains APKBridge state, Waydroid status, and recent Waydroid logs. It does not delete or reset Android data."
        )
        repair_note.setWordWrap(True)
        repair_note.setObjectName("muted")
        repair_layout.addWidget(repair_note)
        repair_buttons = QHBoxLayout()
        report = QPushButton("Create General Diagnostic")
        report.clicked.connect(lambda: self.create_diagnostic(""))
        logs = QPushButton("Open APKBridge Log Folder")
        logs.clicked.connect(self.open_log_folder)
        repair_buttons.addWidget(report)
        repair_buttons.addWidget(logs)
        repair_buttons.addStretch(1)
        repair_layout.addLayout(repair_buttons)
        layout.addWidget(repair)
        layout.addStretch(1)
        return scroll

    def _build_log_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("APKBridge operations will appear here.")
        layout.addWidget(self.log_view, 1)
        row = QHBoxLayout()
        clear = QPushButton("Clear View")
        clear.clicked.connect(self.log_view.clear)
        folder = QPushButton("Open Log Folder")
        folder.clicked.connect(self.open_log_folder)
        row.addWidget(clear)
        row.addWidget(folder)
        row.addStretch(1)
        layout.addLayout(row)
        return page

    def _restore_config(self, initial_apk: str) -> None:
        selected_profile = str(self.config.get("profile") or "Desktop Balanced")
        if selected_profile in PROFILES:
            self.profile_combo.setCurrentText(selected_profile)
        self._profile_changed(self.profile_combo.currentText(), restore_checks=True)
        self.apk_edit.setText(initial_apk or str(self.config.get("apk") or ""))
        self.package_edit.setText(str(self.config.get("package") or ""))
        self.fullscreen.setChecked(bool(self.config.get("fullscreen", False)))
        if "fake_touch" in self.config:
            self.fake_touch.setChecked(bool(self.config["fake_touch"]))
        if "fake_wifi" in self.config:
            self.fake_wifi.setChecked(bool(self.config["fake_wifi"]))
        self.invert_colors.setChecked(bool(self.config.get("invert_colors", False)))

    def _save_config(self) -> None:
        save_config({
            "apk": self.apk_edit.text().strip(),
            "package": self.package_edit.text().strip(),
            "profile": self.profile_combo.currentText(),
            "fullscreen": self.fullscreen.isChecked(),
            "fake_touch": self.fake_touch.isChecked(),
            "fake_wifi": self.fake_wifi.isChecked(),
            "invert_colors": self.invert_colors.isChecked(),
        })

    def _profile_changed(self, name: str, restore_checks: bool = False) -> None:
        profile = PROFILES.get(name)
        if not profile:
            return
        self.profile_description.setText(f"{profile.width}×{profile.height} — {profile.description}")
        if not restore_checks or not self.config:
            self.fake_touch.setChecked(profile.fake_touch)
            self.fake_wifi.setChecked(profile.fake_wifi)

    def _tab_changed(self, index: int) -> None:
        if index == 1 and not self.current_apps:
            self.refresh_apps()

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
        if any(url.toLocalFile().lower().endswith(".apk") for url in urls):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".apk"):
                self.apk_edit.setText(path)
                self.tabs.setCurrentIndex(0)
                self.analyze_selected_apk()
                event.acceptProposedAction()
                return

    def browse_apk(self) -> None:
        start = self.apk_edit.text().strip() or str(Path.home())
        path, _filter = QFileDialog.getOpenFileName(self, "Choose Android APK", start, "Android packages (*.apk);;All files (*)")
        if path:
            self.apk_edit.setText(path)
            self._save_config()
            self.analyze_selected_apk()

    def _apk_edited(self) -> None:
        self._save_config()
        if self.apk_edit.text().strip():
            self.analyze_selected_apk()

    def _set_busy(self, busy: bool, label: str = "") -> None:
        self.progress.setVisible(busy)
        self.footer_status.setText(label if busy else "Ready")

    def start_task(
        self,
        name: str,
        arguments: list[str],
        *,
        root: bool = False,
        script: Path = CORE,
        callback: Callable[[dict[str, Any]], None] | None = None,
        error_callback: Callable[[str], None] | None = None,
        quiet: bool = False,
    ) -> bool:
        if self.process is not None:
            if not quiet:
                QMessageBox.information(self, "APKBridge is busy", f"Wait for “{self.task_name}” to finish first.")
            return False
        command = [sys.executable, str(script), *arguments]
        if root:
            helper = shutil.which("pkexec")
            if not helper:
                QMessageBox.warning(self, "Administrator helper missing", "APKBridge needs pkexec for this system-level action.")
                return False
            command = [helper, *command]
        self.task_name = name
        self.task_output = ""
        self.task_callback = callback
        self.task_error_callback = error_callback
        self.quiet_task = quiet
        self.log_view.appendPlainText(f"\n=== {name} ===")
        self.process = QProcess(self)
        self.process.setProgram(command[0])
        self.process.setArguments(command[1:])
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_process)
        self.process.finished.connect(self._task_finished)
        self.process.errorOccurred.connect(self._process_error)
        self.process.start()
        self._set_busy(True, f"{name}…")
        return True

    def _read_process(self) -> None:
        if not self.process:
            return
        text = bytes(self.process.readAllStandardOutput()).decode(errors="replace")
        if text:
            self.task_output += text
            visible = "\n".join(
                line for line in text.rstrip().splitlines()
                if not line.startswith("APKBRIDGE_JSON=")
            )
            if visible:
                self.log_view.appendPlainText(visible)

    def _process_error(self, error) -> None:
        self.log_view.appendPlainText(f"Process error: {error.name}")

    def _task_finished(self, code: int, _exit_status) -> None:
        if not self.process:
            return
        final = bytes(self.process.readAllStandardOutput()).decode(errors="replace")
        if final:
            self.task_output += final
        payload, marker_error = parse_payload(self.task_output)
        name = self.task_name
        callback = self.task_callback
        error_callback = self.task_error_callback
        quiet = self.quiet_task
        self.log_view.appendPlainText(f"=== {name} finished with code {code} ===")
        self.process.deleteLater()
        self.process = None
        self.task_name = ""
        self.task_callback = None
        self.task_error_callback = None
        self.quiet_task = False
        self._set_busy(False)
        if code == 0 and isinstance(payload, dict):
            if callback:
                callback(payload)
            return
        error = marker_error or self._last_useful_line(self.task_output) or f"{name} failed."
        if error_callback:
            error_callback(error)
        elif not quiet:
            QMessageBox.critical(self, f"{name} failed", error)

    @staticmethod
    def _last_useful_line(text: str) -> str:
        for line in reversed(text.splitlines()):
            line = line.strip()
            if line and not line.startswith(("[", "APKBRIDGE_")):
                return line
        return ""

    def refresh_status(self) -> None:
        self.start_task("Check system", ["status"], callback=self._status_ready, quiet=True)

    def _status_ready(self, data: dict[str, Any]) -> None:
        self.last_status = data
        installed = bool(data.get("waydroid_installed"))
        initialized = bool(data.get("waydroid_initialized"))
        session = str(data.get("session") or "unknown")
        version = str(data.get("waydroid_version") or "")
        self.distro_value.setText(str(data.get("distribution") or "Unknown Linux"))
        if not installed:
            self.waydroid_value.setText("Not installed")
            self.header_status.setText("Setup required")
            self.header_status.setObjectName("statusBad")
        elif not initialized:
            self.waydroid_value.setText(f"Installed {version} — initialization needed")
            self.header_status.setText("Initialization required")
            self.header_status.setObjectName("statusWarn")
        else:
            self.waydroid_value.setText(f"Ready {version}".strip())
            self.header_status.setText("Ready to run APKs")
            self.header_status.setObjectName("statusGood")
        if not data.get("wayland"):
            self.header_status.setText("Wayland session recommended")
            self.header_status.setObjectName("statusWarn")
        self.header_status.style().unpolish(self.header_status)
        self.header_status.style().polish(self.header_status)
        self.session_value.setText(session.title())
        bridge = str(data.get("native_bridge") or "none")
        self.arm_value.setText(bridge if bridge != "none" else "Not installed")

    def analyze_selected_apk(self) -> None:
        path = Path(self.apk_edit.text().strip()).expanduser()
        if not path.is_file():
            self.analysis_label.setText("Choose an existing .apk file first.")
            return
        self._save_config()
        self.start_task("Inspect APK", ["analyze", str(path)], callback=self._analysis_ready)

    def _analysis_ready(self, data: dict[str, Any]) -> None:
        self.last_analysis = data
        abis = ", ".join(data.get("native_abis") or []) or "no bundled native libraries"
        parts = [
            str(data.get("label") or data.get("file_name") or "APK"),
            human_size(int(data.get("size_bytes") or 0)),
            f"native ABI: {abis}",
        ]
        if data.get("version_name"):
            parts.insert(1, f"version {data['version_name']}")
        if data.get("requires_arm_translation"):
            parts.append("ARM translation is likely required on this computer")
        elif data.get("incompatible_native_architecture"):
            parts.append("native CPU architecture may be incompatible")
        else:
            parts.append("CPU check passed")
        self.analysis_label.setText(" • ".join(parts))
        if data.get("package"):
            self.package_edit.setText(str(data["package"]))
        self._save_config()

    def _arm_warning_allows_continue(self) -> bool:
        if not self.last_analysis.get("requires_arm_translation"):
            return True
        if self.last_status.get("native_bridge") in {"libndk", "libhoudini"}:
            return True
        answer = QMessageBox.warning(
            self,
            "ARM compatibility likely required",
            "This APK contains ARM native code, while this computer is x86-64. It may install but probably will not launch until libndk is installed from Setup & Repair.\n\nTry installing it anyway?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.tabs.setCurrentIndex(2)
            return False
        return True

    def install_apk(self, *, launch_after: bool) -> None:
        path = Path(self.apk_edit.text().strip()).expanduser()
        if not path.is_file() or path.suffix.lower() != ".apk":
            QMessageBox.warning(self, "APK not found", "Choose a valid .apk file first.")
            return
        if not self._arm_warning_allows_continue():
            return
        self._save_config()

        def installed(data: dict[str, Any]) -> None:
            package = str(data.get("package") or "")
            if not package:
                package, accepted = QInputDialog.getText(
                    self,
                    "Android package name",
                    "The APK installed, but its package name could not be detected automatically. Enter it below:",
                    text=self.package_edit.text().strip(),
                )
                package = package.strip() if accepted else ""
                if not package:
                    QMessageBox.information(self, "APK installed", "The APK was installed. Enter its package name before launching it.")
                    self.refresh_apps()
                    return
                self.package_edit.setText(package)

                def remembered(_payload: dict[str, Any]) -> None:
                    self._after_install(package, launch_after)

                self.start_task("Save package mapping", ["remember", str(path), package], callback=remembered)
                return
            self.package_edit.setText(package)
            self._after_install(package, launch_after)

        self.start_task("Install APK", ["install", str(path)], callback=installed)

    def _after_install(self, package: str, launch_after: bool) -> None:
        self._save_config()
        self.current_apps = []
        if launch_after:
            QTimer.singleShot(100, self.launch_current)
        else:
            QMessageBox.information(self, "APK installed", f"Installed successfully.\n\nPackage: {package}")
            self.refresh_status()

    def _launch_args(self, package: str, profile: str | None = None) -> list[str]:
        chosen = profile or self.profile_combo.currentText()
        return [
            "launch", package,
            "--profile", chosen,
            "--fullscreen", "on" if self.fullscreen.isChecked() else "off",
            "--fake-touch", "on" if self.fake_touch.isChecked() else "off",
            "--fake-wifi", "on" if self.fake_wifi.isChecked() else "off",
            "--invert-colors", "on" if self.invert_colors.isChecked() else "off",
        ]

    def launch_current(self) -> None:
        package = self.package_edit.text().strip()
        if not package:
            QMessageBox.warning(self, "Package name needed", "Install the APK first or enter its Android package name.")
            return
        self._save_config()
        self.start_task(
            "Launch Android app",
            self._launch_args(package),
            callback=lambda _data: self.footer_status.setText(f"Launched {package}"),
        )

    def set_current_fullscreen(self, enabled: bool) -> None:
        package = self.package_edit.text().strip()
        if not package:
            QMessageBox.warning(self, "Package name needed", "Choose or launch an Android app first.")
            return
        answer = QMessageBox.question(
            self, "Switch Android display mode?",
            "This may restart Android and close all running Android apps. "
            "Save your progress first. The selected app will reopen. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        def done(_data: dict[str, Any]) -> None:
            self.fullscreen.setChecked(enabled)
            self._save_config()
            self.footer_status.setText(
                f"{'Fullscreen' if enabled else 'Windowed mode'} requested for {package}. "
                "Switch back to the Android window to check it.")
        self.start_task(
            "Enter fullscreen" if enabled else "Exit fullscreen",
            ["fullscreen", package, "on" if enabled else "off"], callback=done,
        )

    def create_current_shortcut(self) -> None:
        package = self.package_edit.text().strip()
        if not package:
            QMessageBox.warning(self, "Package name needed", "Install the APK first or enter its Android package name.")
            return
        name = str(self.last_analysis.get("label") or Path(self.apk_edit.text()).stem or package)
        self._create_shortcut(package, name, self.profile_combo.currentText())

    def _create_shortcut(self, package: str, name: str, profile: str) -> None:
        def done(data: dict[str, Any]) -> None:
            QMessageBox.information(self, "Shortcut created", f"Added {name} to your application menu.\n\n{data.get('shortcut', '')}")

        self.start_task("Create app shortcut", ["shortcut", package, "--name", name, "--profile", profile], callback=done)

    def refresh_apps(self) -> None:
        arguments = ["list"]
        if self.managed_only.isChecked():
            arguments.append("--managed-only")
        self.start_task("Refresh Android apps", arguments, callback=self._apps_ready, quiet=True)

    def _apps_ready(self, data: dict[str, Any]) -> None:
        self.current_apps = data.get("apps", []) if isinstance(data.get("apps"), list) else []
        self.app_list.clear()
        for row in self.current_apps:
            if not isinstance(row, dict):
                continue
            suffix = "" if row.get("installed") else " — not currently installed"
            item = QListWidgetItem(f"{row.get('name') or row.get('package')}\n    {row.get('package')}{suffix}")
            item.setData(Qt.ItemDataRole.UserRole, row)
            self.app_list.addItem(item)
        if self.app_list.count() == 0:
            self.app_detail.setText("No matching Android apps were found. Import an APK from the Run APK tab.")

    def _selected_app(self) -> dict[str, Any] | None:
        item = self.app_list.currentItem()
        value = item.data(Qt.ItemDataRole.UserRole) if item else None
        return value if isinstance(value, dict) else None

    def _app_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        row = current.data(Qt.ItemDataRole.UserRole) if current else None
        if not isinstance(row, dict):
            return
        launched = int(row.get("last_launched") or 0)
        launched_text = time.strftime("%Y-%m-%d %H:%M", time.localtime(launched)) if launched else "never"
        abis = ", ".join(row.get("native_abis") or []) or "not recorded"
        self.app_detail.setText(
            f"Package: {row.get('package')}  •  Profile: {row.get('profile')}  •  Native ABI: {abis}  •  Last launched: {launched_text}"
        )

    def launch_library_app(self) -> None:
        row = self._selected_app()
        if not row:
            return
        package = str(row.get("package") or "")
        profile = str(row.get("profile") or "Desktop Balanced")
        self.profile_combo.setCurrentText(profile if profile in PROFILES else "Desktop Balanced")
        self.package_edit.setText(package)
        self.fullscreen.setChecked(bool(row.get("fullscreen", False)))
        self.tabs.setCurrentIndex(0)
        self.launch_current()

    def create_library_shortcut(self) -> None:
        row = self._selected_app()
        if not row:
            return
        self._create_shortcut(
            str(row.get("package") or ""),
            str(row.get("name") or row.get("package") or "Android App"),
            str(row.get("profile") or "Desktop Balanced"),
        )

    def diagnose_library_app(self) -> None:
        row = self._selected_app()
        if row:
            self.create_diagnostic(str(row.get("package") or ""))

    def remove_library_app(self) -> None:
        row = self._selected_app()
        if not row:
            return
        package = str(row.get("package") or "")
        answer = QMessageBox.question(
            self,
            "Uninstall Android app",
            f"Uninstall {row.get('name') or package} from Waydroid?\n\nIts APKBridge record will be kept so the original APK and profile remain known.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.start_task("Uninstall Android app", ["remove", package], callback=lambda _data: self.refresh_apps())

    def install_waydroid(self) -> None:
        answer = QMessageBox.question(
            self,
            "Install Waydroid",
            "Install Waydroid using this computer's package manager?\n\nThis is a system-level change and requires administrator approval. Immutable Fedora/Bazzite systems will require a reboot.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        def done(data: dict[str, Any]) -> None:
            if data.get("reboot_required"):
                QMessageBox.information(self, "Reboot required", "Waydroid was layered successfully. Reboot the computer, then return to APKBridge and choose Initialize Android Image.")
            else:
                QMessageBox.information(self, "Waydroid installed", "Waydroid is installed. The next step is Initialize Android Image.")
            self.refresh_status()

        self.start_task("Install Waydroid", ["setup-waydroid"], root=True, callback=done)

    def initialize_waydroid(self) -> None:
        answer = QMessageBox.question(
            self,
            "Initialize Waydroid",
            "Download and initialize Waydroid's Android system image now?\n\nThis can take several minutes and requires administrator approval.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.start_task(
            "Initialize Android image",
            ["initialize-waydroid"],
            root=True,
            callback=lambda _data: (QMessageBox.information(self, "Initialization complete", "Waydroid's Android image is ready."), self.refresh_status()),
        )

    def start_session(self) -> None:
        self.start_task("Start Waydroid session", ["start"], callback=lambda _data: self.refresh_status())

    def stop_session(self) -> None:
        self.start_task("Stop Waydroid session", ["stop"], callback=lambda _data: self.refresh_status())

    def open_full_ui(self) -> None:
        if not shutil.which("waydroid"):
            QMessageBox.warning(self, "Waydroid missing", "Install Waydroid first.")
            return
        QProcess.startDetached("waydroid", ["show-full-ui"])

    def install_arm(self) -> None:
        answer = QMessageBox.warning(
            self,
            "Install ARM compatibility",
            "APKBridge will download the current GPL-licensed Waydroid Extras Script from casualsnek/waydroid_script, record its exact revision, snapshot Waydroid's configuration, and use it to install libndk.\n\nThis modifies Waydroid system files and requires administrator approval. It is a compatibility aid, not a guarantee that every ARM app will work. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.start_task(
            "Install libndk ARM compatibility",
            ["install", "libndk"],
            root=True,
            script=ARM_HELPER,
            callback=lambda _data: (QMessageBox.information(self, "ARM compatibility installed", "libndk installation completed. Retry the ARM APK now."), self.refresh_status()),
        )

    def remove_arm(self) -> None:
        answer = QMessageBox.question(
            self,
            "Remove ARM compatibility",
            "Remove libndk from Waydroid? Use this rollback if ARM translation causes crashes or graphics problems.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.start_task(
            "Remove libndk ARM compatibility",
            ["remove", "libndk"],
            root=True,
            script=ARM_HELPER,
            callback=lambda _data: self.refresh_status(),
        )

    def create_diagnostic(self, package: str) -> None:
        arguments = ["diagnose"] + ([package] if package else [])

        def done(data: dict[str, Any]) -> None:
            report = str(data.get("report") or "")
            if report:
                answer = QMessageBox.question(self, "Diagnostic created", f"Diagnostic report created:\n\n{report}\n\nOpen it now?")
                if answer == QMessageBox.StandardButton.Yes:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(report))

        self.start_task("Create diagnostic report", arguments, callback=done)

    def open_log_folder(self) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(LOG_DIR)))

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._save_config()
        if self.process:
            answer = QMessageBox.question(self, "Task still running", f"“{self.task_name}” is still running. Close APKBridge anyway?")
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.process.kill()
        event.accept()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Android APKs on Linux through Waydroid")
    parser.add_argument("apk", nargs="?", default="", help="APK to select")
    parser.add_argument("--launch", metavar="PACKAGE", default="", help="Launch an installed Android package")
    parser.add_argument("--profile", choices=list(PROFILES), default="Desktop Balanced")
    parser.add_argument("--version", action="version", version=f"APKBridge {VERSION}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("APKBridge")
    app.setDesktopFileName("apkbridge")
    app.setStyleSheet(APP_STYLE)
    if ICON.is_file():
        app.setWindowIcon(QIcon(str(ICON)))
    if args.launch:
        try:
            launch_package(args.launch, args.profile)
            return 0
        except BridgeError as exc:
            QMessageBox.critical(None, "APKBridge launch failed", str(exc))
            return 1
    window = MainWindow(args.apk)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
