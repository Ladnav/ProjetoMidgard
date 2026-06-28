from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from midgard.profile import ProfileStore
from midgard.runtime.launcher import RuntimeLauncher
from midgard.ui.picker import PickDialog
from midgard.ui.theme import Theme
from midgard.vision.capture import WindowCaptureService


class Page(QWidget):
    """Standard page frame with a heading and one foundation card."""

    def __init__(
        self,
        title: str,
        description: str,
        card_title: str,
        card_body: str,
        *,
        card_eyebrow: str = "FOUNDATION",
    ) -> None:
        super().__init__()
        self.title = title
        self.setObjectName(f"{title.lower()}Page")

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(42, 34, 42, 34)
        page_layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        description_label = QLabel(description)
        description_label.setObjectName("pageDescription")
        description_label.setWordWrap(True)

        page_layout.addWidget(title_label)
        page_layout.addWidget(description_label)
        page_layout.addSpacing(24)

        self.card = QFrame()
        self.card.setObjectName("contentCard")
        self.card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(24, 22, 24, 22)
        self.card_layout.setSpacing(8)

        eyebrow_label = QLabel(card_eyebrow)
        eyebrow_label.setObjectName("cardEyebrow")
        card_title_label = QLabel(card_title)
        card_title_label.setObjectName("cardTitle")
        card_body_label = QLabel(card_body)
        card_body_label.setObjectName("cardBody")
        card_body_label.setWordWrap(True)

        self.card_layout.addWidget(eyebrow_label)
        self.card_layout.addWidget(card_title_label)
        self.card_layout.addWidget(card_body_label)
        page_layout.addWidget(self.card)
        page_layout.addStretch(1)


class SettingsPage(Page):
    """Application appearance settings page."""

    theme_selected = Signal(str)

    def __init__(self, initial_theme: Theme) -> None:
        super().__init__(
            "Settings",
            "Manage local Midgard Studio preferences.",
            "Appearance",
            "Choose the visual theme. The selection is stored locally in SQLite.",
            card_eyebrow="PREFERENCES",
        )

        control_row = QHBoxLayout()
        control_row.setContentsMargins(0, 10, 0, 0)
        theme_label = QLabel("Color theme")
        theme_label.setObjectName("cardBody")

        self.theme_combo = QComboBox()
        self.theme_combo.setObjectName("themeSelector")
        self.theme_combo.addItem("Dark", Theme.DARK.value)
        self.theme_combo.addItem("Light", Theme.LIGHT.value)
        self.set_theme(initial_theme)
        self.theme_combo.currentIndexChanged.connect(self._emit_theme)

        control_row.addWidget(theme_label)
        control_row.addStretch(1)
        control_row.addWidget(self.theme_combo)
        self.card_layout.addLayout(control_row)

    def set_theme(self, theme: Theme) -> None:
        """Synchronize the selector without emitting a user change."""
        index = self.theme_combo.findData(theme.value)
        if index >= 0:
            previous = self.theme_combo.blockSignals(True)
            self.theme_combo.setCurrentIndex(index)
            self.theme_combo.blockSignals(previous)

    def _emit_theme(self) -> None:
        self.theme_selected.emit(str(self.theme_combo.currentData()))


class RuntimeWorker(QThread):
    """Worker thread that consumes TCP socket events from RuntimeLauncher."""

    log_received = Signal(str, str)  # message, level
    status_received = Signal(dict)
    alarm_received = Signal(str, str)  # alarm_type, message
    finished = Signal()

    def __init__(self, launcher: RuntimeLauncher) -> None:
        super().__init__()
        self.launcher = launcher
        self._running = True

    def run(self) -> None:
        while self._running and self.launcher.is_alive():
            try:
                event = self.launcher.receive_event(timeout=0.05)
                if event:
                    if event["type"] == "log":
                        self.log_received.emit(event["message"], event.get("level", "INFO"))
                    elif event["type"] == "status":
                        self.status_received.emit(event)
                    elif event["type"] == "alarm":
                        self.alarm_received.emit(event["alarm_type"], event["message"])
            except Exception:
                pass
        self.finished.emit()

    def stop(self) -> None:
        self._running = False


class RuntimePage(Page):
    """Runtime page that controls character automation engine loops."""

    def __init__(self, profile_store: ProfileStore) -> None:
        super().__init__(
            "Runtime",
            "Monitor active automation sessions and telemetry.",
            "Runtime Control",
            "Select a character profile and control the automation runtime below.",
            card_eyebrow="AUTOMATION",
        )
        self.profile_store = profile_store
        self.launcher: RuntimeLauncher | None = None
        self.worker: RuntimeWorker | None = None

        # 1. Profile selector layout
        selector_layout = QHBoxLayout()
        selector_label = QLabel("Active Profile:")
        self.profile_combo = QComboBox()
        selector_layout.addWidget(selector_label)
        selector_layout.addWidget(self.profile_combo, 1)
        self.card_layout.addLayout(selector_layout)

        # 2. Control buttons layout
        controls_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self._start_runtime)
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self._pause_runtime)
        self.pause_btn.setEnabled(False)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self._stop_runtime)
        self.stop_btn.setEnabled(False)

        controls_layout.addWidget(self.start_btn)
        controls_layout.addWidget(self.pause_btn)
        controls_layout.addWidget(self.stop_btn)
        self.card_layout.addLayout(controls_layout)

        # 3. Telemetry card layout
        telemetry_frame = QFrame()
        telemetry_frame.setObjectName("contentCard")
        tele_layout = QHBoxLayout(telemetry_frame)
        self.status_lbl = QLabel("Status: Idle")
        self.xp_lbl = QLabel("XP Gained: 0")
        self.loot_lbl = QLabel("Loot: 0")
        self.hp_lbl = QLabel("HP: --%")

        tele_layout.addWidget(self.status_lbl)
        tele_layout.addWidget(self.xp_lbl)
        tele_layout.addWidget(self.loot_lbl)
        tele_layout.addWidget(self.hp_lbl)
        self.card_layout.addWidget(telemetry_frame)

        # 4. Live log terminal styling
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        # Apply premium monospaced dark terminal style
        self.terminal.setStyleSheet(
            "background-color: #0b0f19;"
            "color: #10b981;"
            "font-family: 'Consolas', 'Courier New', monospace;"
            "font-size: 11pt;"
            "border: 1px solid #1e293b;"
            "border-radius: 4px;"
            "padding: 8px;"
        )
        self.terminal.setMinimumHeight(240)
        self.card_layout.addWidget(self.terminal)

        # Refresh profile list
        self.refresh_profiles()

    def refresh_profiles(self) -> None:
        """Reload profile names from database."""
        self.profile_combo.clear()
        profiles = self.profile_store.list_profiles()
        for p in profiles:
            self.profile_combo.addItem(p.name, p.id)

    def showEvent(self, event) -> None:
        """Triggered when user clicks the navigation tab to view this page."""
        super().showEvent(event)
        self.refresh_profiles()

    def _start_runtime(self) -> None:
        """Launch the background character engine subprocess."""
        profile_id = self.profile_combo.currentData()
        if profile_id is None:
            QMessageBox.warning(self, "No Profile", "Create a profile first.")
            return

        # Clean up any existing running launcher
        self._cleanup_launcher()

        import sys

        use_dummy = "--dummy-input" in sys.argv

        try:
            self.launcher = RuntimeLauncher(
                profile_id=profile_id,
                database_path=self.profile_store.database_path,
                use_dummy_input=use_dummy,
            )
            self.launcher.start()

            # Enable/disable buttons
            self.start_btn.setEnabled(False)
            self.pause_btn.setEnabled(True)
            self.stop_btn.setEnabled(True)
            self.profile_combo.setEnabled(False)

            self.status_lbl.setText("Status: Starting...")
            self.terminal.clear()
            self.terminal.append(">>> Starting Runtime launcher process...")

            # Start worker thread
            self.worker = RuntimeWorker(self.launcher)
            self.worker.log_received.connect(self._on_log_received)
            self.worker.status_received.connect(self._on_status_received)
            self.worker.alarm_received.connect(self._on_alarm_received)
            self.worker.finished.connect(self._on_worker_finished)
            self.worker.start()
        except Exception as e:
            QMessageBox.critical(self, "Launch Error", f"Failed to start engine: {e}")
            self._cleanup_launcher()

    def _pause_runtime(self) -> None:
        """Toggle active/paused engine ticks execution state."""
        if self.launcher and self.launcher.is_alive():
            if self.pause_btn.text() == "Pause":
                self.launcher.send_command("pause")
                self.pause_btn.setText("Resume")
                self.status_lbl.setText("Status: Paused")
            else:
                self.launcher.send_command("start")
                self.pause_btn.setText("Pause")
                self.status_lbl.setText("Status: Running")

    def _stop_runtime(self) -> None:
        """Gracefully request engine stop and process termination."""
        if self.launcher:
            self.launcher.send_command("stop")
            self.terminal.append(">>> Sent stop command to engine process.")
            self.pause_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)

    def _on_log_received(self, message: str, level: str) -> None:
        if "registration" in message.lower() or "connected" in message.lower():
            if self.launcher:
                self.launcher.send_command("start")
                self.status_lbl.setText("Status: Running")

        prefix = f"[{level}] " if level else ""
        self.terminal.append(f"{prefix}{message}")

    def _on_status_received(self, status: dict) -> None:
        hp = status.get("hp_pct", 100)
        xp = status.get("xp_gained", 0)
        loot = status.get("loot_collected", 0)

        self.hp_lbl.setText(f"HP: {hp}%")
        self.xp_lbl.setText(f"XP Gained: {xp}")
        self.loot_lbl.setText(f"Loot: {loot}")

        if hp < 30:
            self.hp_lbl.setStyleSheet("color: #ef4444; font-weight: bold;")
        else:
            self.hp_lbl.setStyleSheet("")

    def _on_worker_finished(self) -> None:
        self.status_lbl.setText("Status: Stopped")
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("Pause")
        self.stop_btn.setEnabled(False)
        self.profile_combo.setEnabled(True)
        self.terminal.append(">>> Engine launcher process terminated.")

    def _on_alarm_received(self, alarm_type: str, message: str) -> None:
        """Handle critical alarm events from the runtime engine."""
        from PySide6.QtWidgets import QApplication

        # Play system audio alert
        QApplication.beep()

        # Format alert in the terminal with red HTML styling
        alarm_html = (
            f'<span style="color:#ef4444; font-weight:bold;">'
            f"\u26a0 ALARM [{alarm_type.upper()}]: {message}</span>"
        )
        self.terminal.append(alarm_html)

        # Flash the status label red
        self.status_lbl.setStyleSheet("color: #ef4444; font-weight: bold;")
        if alarm_type == "death":
            self.status_lbl.setText("Status: 💀 CHARACTER DEATH DETECTED")
        elif alarm_type == "disconnect":
            self.status_lbl.setText("Status: ⚡ CLIENT DISCONNECTED")

    def _cleanup_launcher(self) -> None:
        """Clean up the worker thread and terminate launcher process."""
        if self.worker:
            self.worker.stop()
            self.worker.wait()
            self.worker = None

        if self.launcher:
            self.launcher.terminate()
            self.launcher = None

    def closeEvent(self, event) -> None:
        self._cleanup_launcher()
        super().closeEvent(event)


class LogsPage(Page):
    """Placeholder page that identifies the active application log file."""

    def __init__(self, log_path: Path) -> None:
        super().__init__(
            "Logs",
            "Application diagnostics are recorded locally.",
            "Logger ready",
            f"Current log file: {log_path}",
            card_eyebrow="DIAGNOSTICS",
        )


class AboutPage(Page):
    """Product identity and version page."""

    def __init__(self, version: str) -> None:
        super().__init__(
            "About",
            "Product and build information.",
            "Midgard Studio",
            f"Version {version}\n\nA modular desktop foundation for Project Midgard.",
            card_eyebrow="PROJECT MIDGARD",
        )


class ProfilesPage(Page):
    """Profiles management page with rules editor form tabs."""

    def __init__(self, profile_store: ProfileStore) -> None:
        super().__init__(
            "Profiles",
            "Manage character profiles and active rules rules.",
            "Profiles Manager",
            "Select a character profile below to customize its automation parameters.",
            card_eyebrow="PROFILES",
        )
        self.profile_store = profile_store

        # 1. Profile selector row
        selector_layout = QHBoxLayout()
        selector_layout.setContentsMargins(0, 10, 0, 10)

        selector_label = QLabel("Active Profile:")
        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self._load_profile_rules)
        selector_layout.addWidget(selector_label)
        selector_layout.addWidget(self.profile_combo, 1)

        self.new_profile_input = QLineEdit()
        self.new_profile_input.setPlaceholderText("New Character Name")
        create_button = QPushButton("Create Profile")
        create_button.clicked.connect(self._create_new_profile)
        selector_layout.addWidget(self.new_profile_input)
        selector_layout.addWidget(create_button)

        self.card_layout.addLayout(selector_layout)

        # 2. Rule configuration Tab Widget
        self.tab_widget = QTabWidget()
        self.card_layout.addWidget(self.tab_widget)

        # Initialize Forms for tabs
        self._init_healing_tab()
        self._init_consumables_tab()
        self._init_combat_tab()
        self._init_navigation_tab()

        # 3. Save Button
        self.save_button = QPushButton("Save Profile Rules")
        self.save_button.clicked.connect(self._save_profile_rules)
        self.card_layout.addWidget(self.save_button)

        # Load initial profiles from database
        self._reload_profiles()

    def _reload_profiles(self) -> None:
        """Fetch profiles from SQLite and refresh the selector."""
        previous = self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        profiles = self.profile_store.list_profiles()
        for p in profiles:
            self.profile_combo.addItem(p.name, p.id)
        self.profile_combo.blockSignals(previous)
        self._load_profile_rules()

    def _create_new_profile(self) -> None:
        """Insert a new profile into the database."""
        name = self.new_profile_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Invalid Name", "Profile name cannot be empty.")
            return

        try:
            self.profile_store.create_profile(name)
            self.new_profile_input.clear()
            self._reload_profiles()
            # Select the newly created profile
            index = self.profile_combo.findText(name)
            if index >= 0:
                self.profile_combo.setCurrentIndex(index)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create profile: {e}")

    def _init_healing_tab(self) -> None:
        tab = QWidget()
        layout = QFormLayout(tab)

        self.heal_enabled = QCheckBox("Enable Healing")
        self.heal_hp_threshold = QSpinBox()
        self.heal_hp_threshold.setRange(1, 100)
        self.heal_hp_key = QComboBox()
        self.heal_hp_key.addItems([f"F{i}" for i in range(1, 11)])

        self.heal_hp_x = QSpinBox()
        self.heal_hp_x.setRange(0, 5000)
        self.heal_hp_y = QSpinBox()
        self.heal_hp_y.setRange(0, 5000)

        self.heal_expected_r = QSpinBox()
        self.heal_expected_r.setRange(0, 255)
        self.heal_expected_g = QSpinBox()
        self.heal_expected_g.setRange(0, 255)
        self.heal_expected_b = QSpinBox()
        self.heal_expected_b.setRange(0, 255)

        self.heal_color_tolerance = QSpinBox()
        self.heal_color_tolerance.setRange(0, 255)

        self.heal_min_cooldown = QDoubleSpinBox()
        self.heal_min_cooldown.setRange(0.0, 10.0)
        self.heal_max_cooldown = QDoubleSpinBox()
        self.heal_max_cooldown.setRange(0.0, 10.0)

        layout.addRow(self.heal_enabled)
        layout.addRow("HP Trigger Threshold (%)", self.heal_hp_threshold)
        layout.addRow("Healing Potion Hotkey", self.heal_hp_key)

        coord_layout = QHBoxLayout()
        coord_layout.addWidget(QLabel("X:"))
        coord_layout.addWidget(self.heal_hp_x)
        coord_layout.addWidget(QLabel("Y:"))
        coord_layout.addWidget(self.heal_hp_y)
        self.heal_pick_btn = QPushButton("Pick Coords & Color")
        self.heal_pick_btn.clicked.connect(self._pick_healing_pixel)
        coord_layout.addWidget(self.heal_pick_btn)
        layout.addRow("HP Bar Coordinates", coord_layout)

        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("R:"))
        color_layout.addWidget(self.heal_expected_r)
        color_layout.addWidget(QLabel("G:"))
        color_layout.addWidget(self.heal_expected_g)
        color_layout.addWidget(QLabel("B:"))
        color_layout.addWidget(self.heal_expected_b)
        layout.addRow("Expected Active RGB Color", color_layout)

        layout.addRow("Color Match Tolerance", self.heal_color_tolerance)

        cd_layout = QHBoxLayout()
        cd_layout.addWidget(QLabel("Min (s):"))
        cd_layout.addWidget(self.heal_min_cooldown)
        cd_layout.addWidget(QLabel("Max (s):"))
        cd_layout.addWidget(self.heal_max_cooldown)
        layout.addRow("Action Delay Cooldowns", cd_layout)

        self.tab_widget.addTab(tab, "Healing")

    def _init_consumables_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.consumables_enabled = QCheckBox("Enable Consumables & Buffs")
        layout.addWidget(self.consumables_enabled)

        label = QLabel("Consumables List Configuration (format: name,key,duration;...):")
        layout.addWidget(label)

        self.consumables_text = QTextEdit()
        self.consumables_text.setPlaceholderText("e.g. concentration,F5,1800.0;agi_up,F6,240.0")
        layout.addWidget(self.consumables_text)

        self.tab_widget.addTab(tab, "Consumables")

    def _init_combat_tab(self) -> None:
        tab = QWidget()
        layout = QFormLayout(tab)

        self.combat_enabled = QCheckBox("Enable Target Combat")
        self.combat_target_r = QSpinBox()
        self.combat_target_r.setRange(0, 255)
        self.combat_target_g = QSpinBox()
        self.combat_target_g.setRange(0, 255)
        self.combat_target_b = QSpinBox()
        self.combat_target_b.setRange(0, 255)

        self.combat_color_tolerance = QSpinBox()
        self.combat_color_tolerance.setRange(0, 255)

        self.combat_step_x = QSpinBox()
        self.combat_step_x.setRange(1, 50)
        self.combat_step_y = QSpinBox()
        self.combat_step_y.setRange(1, 50)

        self.combat_min_hits = QSpinBox()
        self.combat_min_hits.setRange(1, 100)

        self.combat_min_cooldown = QDoubleSpinBox()
        self.combat_min_cooldown.setRange(0.0, 10.0)
        self.combat_max_cooldown = QDoubleSpinBox()
        self.combat_max_cooldown.setRange(0.0, 10.0)

        layout.addRow(self.combat_enabled)

        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("R:"))
        color_layout.addWidget(self.combat_target_r)
        color_layout.addWidget(QLabel("G:"))
        color_layout.addWidget(self.combat_target_g)
        color_layout.addWidget(QLabel("B:"))
        color_layout.addWidget(self.combat_target_b)
        self.combat_pick_btn = QPushButton("Pick Color")
        self.combat_pick_btn.clicked.connect(self._pick_combat_color)
        color_layout.addWidget(self.combat_pick_btn)
        layout.addRow("Target RGB Color", color_layout)

        layout.addRow("Color Match Tolerance", self.combat_color_tolerance)

        step_layout = QHBoxLayout()
        step_layout.addWidget(QLabel("Step X:"))
        step_layout.addWidget(self.combat_step_x)
        step_layout.addWidget(QLabel("Step Y:"))
        step_layout.addWidget(self.combat_step_y)
        layout.addRow("Grid Scan Steps", step_layout)

        layout.addRow("Min Match Pixels (Hits)", self.combat_min_hits)

        cd_layout = QHBoxLayout()
        cd_layout.addWidget(QLabel("Min (s):"))
        cd_layout.addWidget(self.combat_min_cooldown)
        cd_layout.addWidget(QLabel("Max (s):"))
        cd_layout.addWidget(self.combat_max_cooldown)
        layout.addRow("Action Cooldowns", cd_layout)

        self.tab_widget.addTab(tab, "Combat")

    def _init_navigation_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.nav_enabled = QCheckBox("Enable Waypoint Navigation")
        layout.addWidget(self.nav_enabled)

        label = QLabel("Waypoints Path Coordinates (format: x,y,wait;...):")
        layout.addWidget(label)

        self.nav_waypoints_text = QTextEdit()
        self.nav_waypoints_text.setPlaceholderText("e.g. 200,200,3.0;400,200,4.0")
        layout.addWidget(self.nav_waypoints_text)

        self.tab_widget.addTab(tab, "Navigation")

    def _load_profile_rules(self) -> None:
        """Populate rule form fields with values from database or fallbacks to defaults."""
        profile_id = self.profile_combo.currentData()
        if profile_id is None:
            return

        profile = self.profile_store.get_profile(profile_id)
        if not profile:
            return

        rules = profile.rules

        # Load Healing rules
        heal = rules.get("healing", {})
        self.heal_enabled.setChecked(heal.get("heal.enabled", "false").lower() == "true")
        self.heal_hp_threshold.setValue(int(heal.get("heal.hp_threshold", "70")))
        self.heal_hp_key.setCurrentText(heal.get("heal.hp_key", "F1"))
        self.heal_hp_x.setValue(int(heal.get("heal.hp_x", "100")))
        self.heal_hp_y.setValue(int(heal.get("heal.hp_y", "50")))
        self.heal_expected_r.setValue(int(heal.get("heal.expected_hp_r", "0")))
        self.heal_expected_g.setValue(int(heal.get("heal.expected_hp_g", "255")))
        self.heal_expected_b.setValue(int(heal.get("heal.expected_hp_b", "0")))
        self.heal_color_tolerance.setValue(int(heal.get("heal.color_tolerance", "30")))
        self.heal_min_cooldown.setValue(float(heal.get("heal.min_cooldown", "0.5")))
        self.heal_max_cooldown.setValue(float(heal.get("heal.max_cooldown", "0.8")))

        # Load Consumables rules
        cons = rules.get("consumables", {})
        self.consumables_enabled.setChecked(
            cons.get("consumables.enabled", "false").lower() == "true"
        )
        self.consumables_text.setPlainText(cons.get("consumables.items", ""))

        # Load Combat rules
        combat = rules.get("combat", {})
        self.combat_enabled.setChecked(combat.get("combat.enabled", "false").lower() == "true")
        self.combat_target_r.setValue(int(combat.get("combat.target_r", "255")))
        self.combat_target_g.setValue(int(combat.get("combat.target_g", "0")))
        self.combat_target_b.setValue(int(combat.get("combat.target_b", "0")))
        self.combat_color_tolerance.setValue(int(combat.get("combat.color_tolerance", "30")))
        self.combat_step_x.setValue(int(combat.get("combat.step_x", "5")))
        self.combat_step_y.setValue(int(combat.get("combat.step_y", "5")))
        self.combat_min_hits.setValue(int(combat.get("combat.min_hits", "3")))
        self.combat_min_cooldown.setValue(float(combat.get("combat.min_cooldown", "1.0")))
        self.combat_max_cooldown.setValue(float(combat.get("combat.max_cooldown", "2.0")))

        # Load Navigation rules
        nav = rules.get("navigation", {})
        self.nav_enabled.setChecked(nav.get("navigation.enabled", "false").lower() == "true")
        self.nav_waypoints_text.setPlainText(nav.get("navigation.waypoints", ""))

    def _save_profile_rules(self) -> None:
        """Persist rule configuration fields to the SQLite profile database."""
        profile_id = self.profile_combo.currentData()
        if profile_id is None:
            QMessageBox.warning(self, "No Profile", "Create or select a profile first.")
            return

        try:
            # 1. Save Healing rules
            self.profile_store.set_rule(
                profile_id, "healing", "heal.enabled", str(self.heal_enabled.isChecked()).lower()
            )
            self.profile_store.set_rule(
                profile_id,
                "healing",
                "heal.hp_threshold",
                str(self.heal_hp_threshold.value()),
            )
            self.profile_store.set_rule(
                profile_id, "healing", "heal.hp_key", self.heal_hp_key.currentText()
            )
            self.profile_store.set_rule(
                profile_id, "healing", "heal.hp_x", str(self.heal_hp_x.value())
            )
            self.profile_store.set_rule(
                profile_id, "healing", "heal.hp_y", str(self.heal_hp_y.value())
            )
            self.profile_store.set_rule(
                profile_id, "healing", "heal.expected_hp_r", str(self.heal_expected_r.value())
            )
            self.profile_store.set_rule(
                profile_id, "healing", "heal.expected_hp_g", str(self.heal_expected_g.value())
            )
            self.profile_store.set_rule(
                profile_id, "healing", "heal.expected_hp_b", str(self.heal_expected_b.value())
            )
            self.profile_store.set_rule(
                profile_id,
                "healing",
                "heal.color_tolerance",
                str(self.heal_color_tolerance.value()),
            )
            self.profile_store.set_rule(
                profile_id, "healing", "heal.min_cooldown", str(self.heal_min_cooldown.value())
            )
            self.profile_store.set_rule(
                profile_id, "healing", "heal.max_cooldown", str(self.heal_max_cooldown.value())
            )

            # 2. Save Consumables rules
            self.profile_store.set_rule(
                profile_id,
                "consumables",
                "consumables.enabled",
                str(self.consumables_enabled.isChecked()).lower(),
            )
            self.profile_store.set_rule(
                profile_id,
                "consumables",
                "consumables.items",
                self.consumables_text.toPlainText().strip(),
            )

            # 3. Save Combat rules
            self.profile_store.set_rule(
                profile_id, "combat", "combat.enabled", str(self.combat_enabled.isChecked()).lower()
            )
            self.profile_store.set_rule(
                profile_id, "combat", "combat.target_r", str(self.combat_target_r.value())
            )
            self.profile_store.set_rule(
                profile_id, "combat", "combat.target_g", str(self.combat_target_g.value())
            )
            self.profile_store.set_rule(
                profile_id, "combat", "combat.target_b", str(self.combat_target_b.value())
            )
            self.profile_store.set_rule(
                profile_id,
                "combat",
                "combat.color_tolerance",
                str(self.combat_color_tolerance.value()),
            )
            self.profile_store.set_rule(
                profile_id, "combat", "combat.step_x", str(self.combat_step_x.value())
            )
            self.profile_store.set_rule(
                profile_id, "combat", "combat.step_y", str(self.combat_step_y.value())
            )
            self.profile_store.set_rule(
                profile_id, "combat", "combat.min_hits", str(self.combat_min_hits.value())
            )
            self.profile_store.set_rule(
                profile_id, "combat", "combat.min_cooldown", str(self.combat_min_cooldown.value())
            )
            self.profile_store.set_rule(
                profile_id, "combat", "combat.max_cooldown", str(self.combat_max_cooldown.value())
            )

            # 4. Save Navigation rules
            self.profile_store.set_rule(
                profile_id,
                "navigation",
                "navigation.enabled",
                str(self.nav_enabled.isChecked()).lower(),
            )
            self.profile_store.set_rule(
                profile_id,
                "navigation",
                "navigation.waypoints",
                self.nav_waypoints_text.toPlainText().strip(),
            )

            QMessageBox.information(self, "Success", "Profile automation rules saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save rules: {e}")

    def _capture_game_window(self) -> QPixmap | None:
        """Capture the profile's target game window or fallbacks to primary screen."""
        profile_id = self.profile_combo.currentData()
        if profile_id is None:
            QMessageBox.warning(self, "No Profile", "Select a profile first.")
            return None

        profile = self.profile_store.get_profile(profile_id)
        if not profile or not profile.window_title:
            QMessageBox.warning(self, "No Title", "Configure a game window title first.")
            return None

        try:
            capture_service = WindowCaptureService.from_title(profile.window_title)
            pil_img = capture_service.capture()
            # Convert PIL Image to QPixmap
            pil_img = pil_img.convert("RGBA")
            data = bytes(pil_img.tobytes("raw", "RGBA"))
            qimg = QImage(data, pil_img.width(), pil_img.height(), QImage.Format.Format_RGBA8888)
            return QPixmap.fromImage(qimg)
        except Exception as e:
            QMessageBox.warning(
                self,
                "Capture Fallback",
                f"Could not connect to window '{profile.window_title}' ({e}).\n"
                "Falling back to capturing the primary screen monitor.",
            )
            from PySide6.QtGui import QGuiApplication

            screen = QGuiApplication.primaryScreen()
            if screen:
                return screen.grabWindow(0)
            return None

    def _pick_healing_pixel(self) -> None:
        """Show color picker to capture HP coordinates and expected color."""
        pixmap = self._capture_game_window()
        if pixmap is None:
            return
        dialog = PickDialog(pixmap, self)
        if dialog.exec() == QDialog.Accepted:
            if dialog.selected_x is not None:
                self.heal_hp_x.setValue(dialog.selected_x)
                self.heal_hp_y.setValue(dialog.selected_y)
                self.heal_expected_r.setValue(dialog.selected_r)
                self.heal_expected_g.setValue(dialog.selected_g)
                self.heal_expected_b.setValue(dialog.selected_b)

    def _pick_combat_color(self) -> None:
        """Show color picker to capture combat target color."""
        pixmap = self._capture_game_window()
        if pixmap is None:
            return
        dialog = PickDialog(pixmap, self)
        if dialog.exec() == QDialog.Accepted:
            if dialog.selected_r is not None:
                self.combat_target_r.setValue(dialog.selected_r)
                self.combat_target_g.setValue(dialog.selected_g)
                self.combat_target_b.setValue(dialog.selected_b)
