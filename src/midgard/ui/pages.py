from pathlib import Path
from PIL import Image

from PySide6.QtCore import Qt, QThread, Signal
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
from midgard.ui.picker import PickDialog, WindowListDialog
from midgard.ui.theme import Theme
from midgard.vision.capture import (
    WindowCaptureService,
    list_windows_by_title_with_pid,
)


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

    def __init__(self, initial_theme: Theme, settings_store = None) -> None:
        super().__init__(
            "Settings",
            "Manage local Midgard Studio preferences.",
            "Appearance",
            "Choose the visual theme. The selection is stored locally in SQLite.",
            card_eyebrow="PREFERENCES",
        )
        self.settings_store = settings_store

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

        # GameGuard Evasion configurations (TASK-026)
        self.card_layout.addSpacing(15)
        self.fallback_chk = QCheckBox("GameGuard Evasion: Desktop Capture Fallback")
        self.fallback_chk.setToolTip(
            "Captures target bounds from overall desktop display coordinate crops "
            "to avoid triggering protected GDI process window hooks."
        )
        if self.settings_store:
            saved = self.settings_store.get("evasion.desktop_fallback", "false").lower() == "true"
            self.fallback_chk.setChecked(saved)
        self.fallback_chk.stateChanged.connect(self._save_evasion_setting)
        self.card_layout.addWidget(self.fallback_chk)

    def _save_evasion_setting(self, state: int) -> None:
        if self.settings_store:
            enabled_str = str(self.fallback_chk.isChecked()).lower()
            self.settings_store.set("evasion.desktop_fallback", enabled_str)

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

        # Persist dynamic stats incrementally inside SQLite
        profile_id = self.profile_combo.currentData()
        if profile_id is not None:
            try:
                # Assume 1 second elapsed per telemetry update tick
                profile = self.profile_store.get_profile(profile_id)
                deaths = profile.stats.deaths if (profile and profile.stats) else 0
                r_sec = (
                    (profile.stats.runtime_seconds + 1.0) if (profile and profile.stats) else 1.0
                )
                self.profile_store.update_stats(
                    profile_id=profile_id,
                    experience_gained=xp,
                    deaths=deaths,
                    loot_count=loot,
                    runtime_seconds=r_sec,
                )
            except Exception:
                pass

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
            # Update death count in SQLite
            profile_id = self.profile_combo.currentData()
            if profile_id is not None:
                try:
                    profile = self.profile_store.get_profile(profile_id)
                    if profile and profile.stats:
                        self.profile_store.update_stats(
                            profile_id=profile_id,
                            experience_gained=profile.stats.experience_gained,
                            deaths=profile.stats.deaths + 1,
                            loot_count=profile.stats.loot_count,
                            runtime_seconds=profile.stats.runtime_seconds,
                        )
                except Exception:
                    pass
        elif alarm_type == "disconnect":
            self.status_lbl.setText("Status: ⚡ CLIENT DISCONNECTED")
        elif alarm_type == "template_match":
            self.status_lbl.setText("Status: 👁️ VISUAL STATE DETECTED")

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
    """Page for viewing and searching application diagnostics log files."""

    def __init__(self, log_path: Path) -> None:
        super().__init__(
            "Logs",
            "Application diagnostics are recorded locally.",
            "Diagnostics Viewer",
            f"Active log file: {log_path}",
            card_eyebrow="DIAGNOSTICS",
        )
        self.log_path = log_path

        # Create control bar layout
        control_layout = QHBoxLayout()
        control_layout.setContentsMargins(0, 10, 0, 10)

        # 1. Search filter input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter logs by text...")
        self.search_input.textChanged.connect(self._load_and_filter_logs)
        control_layout.addWidget(self.search_input, 1)

        # 2. Level filter dropdown
        self.level_combo = QComboBox()
        self.level_combo.addItem("All Levels", "ALL")
        self.level_combo.addItem("Info", "INFO")
        self.level_combo.addItem("Warning", "WARNING")
        self.level_combo.addItem("Error", "ERROR")
        self.level_combo.currentIndexChanged.connect(self._load_and_filter_logs)
        control_layout.addWidget(self.level_combo)

        # 3. Reload button
        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self._load_and_filter_logs)
        control_layout.addWidget(reload_btn)

        # 4. Clear button
        clear_btn = QPushButton("Clear File")
        clear_btn.clicked.connect(self._clear_log_file)
        control_layout.addWidget(clear_btn)

        self.card_layout.addLayout(control_layout)

        # 5. Log text browser
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setStyleSheet(
            "background-color: #0b0f19;"
            "color: #cbd5e1;"
            "font-family: 'Consolas', 'Courier New', monospace;"
            "font-size: 10pt;"
            "border: 1px solid #1e293b;"
            "border-radius: 4px;"
            "padding: 8px;"
        )
        self.log_viewer.setMinimumHeight(350)
        self.card_layout.addWidget(self.log_viewer)

        # Load initial logs
        self._load_and_filter_logs()

    def showEvent(self, event) -> None:
        """Reload logs whenever page is loaded/navigated."""
        super().showEvent(event)
        self._load_and_filter_logs()

    def _load_and_filter_logs(self) -> None:
        """Read logs file, filter by search text and severity level, and display."""
        if not self.log_path.exists():
            self.log_viewer.setPlainText("Log file does not exist yet.")
            return

        search_query = self.search_input.text().lower()
        level_filter = self.level_combo.currentData()

        filtered_lines = []
        try:
            with open(self.log_path, encoding="utf-8") as f:
                # Read last 500 lines to avoid UI hanging
                lines = f.readlines()[-500:]
                for line in lines:
                    line_lower = line.lower()
                    if search_query and search_query not in line_lower:
                        continue
                    if level_filter != "ALL":
                        if f"[{level_filter}]" not in line and f" - {level_filter} - " not in line:
                            # Also check lowercase representation
                            if f" {level_filter.lower()} " not in line_lower:
                                continue
                    filtered_lines.append(line.strip())
        except OSError as e:
            self.log_viewer.setPlainText(f"Failed to read log file: {e}")
            return

        if filtered_lines:
            self.log_viewer.setPlainText("\n".join(filtered_lines))
        else:
            self.log_viewer.setPlainText("No logs matched the selected filters.")

        # Auto scroll to bottom
        scrollbar = self.log_viewer.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _clear_log_file(self) -> None:
        """Truncate the log file to clean up space."""
        if self.log_path.exists():
            try:
                with open(self.log_path, "w", encoding="utf-8") as f:
                    f.truncate(0)
                self._load_and_filter_logs()
            except OSError as e:
                QMessageBox.critical(self, "Error", f"Failed to clear log file")


class StatisticsTrendChart(QWidget):
    """Draws custom linear line charts of historical XP gains and loot items collected."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(240)
        self.xp_data = [0]
        self.loot_data = [0]
        self.hover_x = -1
        self.setMouseTracking(True)  # Enable hover mouse movement tracking

    def set_data(self, xp_history: list[int], loot_history: list[int]) -> None:
        self.xp_data = xp_history if xp_history else [0]
        self.loot_data = loot_history if loot_history else [0]
        self.update()  # Request Qt canvas repaint event

    def mouseMoveEvent(self, event) -> None:
        self.hover_x = event.position().x()
        self.update()

    def leaveEvent(self, event) -> None:
        self.hover_x = -1
        self.update()

    def paintEvent(self, event) -> None:
        from PySide6.QtGui import QPainter, QPen, QColor, QFont
        from PySide6.QtCore import Qt, QRectF
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Fill chart area background
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor(30, 30, 35))
        
        # Grid line bounds
        pad_l, pad_t, pad_r, pad_b = 50, 20, 20, 30
        chart_w = w - pad_l - pad_r
        chart_h = h - pad_t - pad_b
        
        # Draw background grid lines
        grid_pen = QPen(QColor(60, 60, 65), 1, Qt.PenStyle.DashLine)
        painter.setPen(grid_pen)
        for i in range(5):
            gy = pad_t + int(chart_h * i / 4)
            painter.drawLine(pad_l, gy, w - pad_r, gy)
            
        # Draw axis bounds
        axis_pen = QPen(QColor(150, 150, 160), 2)
        painter.setPen(axis_pen)
        painter.drawLine(pad_l, pad_t, pad_l, h - pad_b)
        painter.drawLine(pad_l, h - pad_b, w - pad_r, h - pad_b)
        
        # Draw XP Line (Green)
        max_xp = max(self.xp_data) if max(self.xp_data) > 0 else 100
        xp_points = []
        for i, val in enumerate(self.xp_data):
            cx = pad_l + int(chart_w * i / max(1, len(self.xp_data) - 1))
            cy = h - pad_b - int(chart_h * val / max_xp)
            xp_points.append((cx, cy))
            
        xp_pen = QPen(QColor(46, 204, 113), 2)
        painter.setPen(xp_pen)
        for i in range(len(xp_points) - 1):
            p1 = xp_points[i]
            p2 = xp_points[i + 1]
            painter.drawLine(p1[0], p1[1], p2[0], p2[1])

        # Draw Loot Bars (Blue)
        max_loot = max(self.loot_data) if max(self.loot_data) > 0 else 10
        bar_w = max(5, int(chart_w / (2 * max(1, len(self.loot_data)))))
        for i, val in enumerate(self.loot_data):
            cx = pad_l + int(chart_w * i / max(1, len(self.loot_data))) + bar_w // 2
            bar_h = int(chart_h * val / max_loot)
            painter.fillRect(cx, h - pad_b - bar_h, bar_w, bar_h, QColor(52, 152, 219))
            
        # Draw Interactive Hover Tooltip (TASK-031)
        if self.hover_x >= pad_l and self.hover_x <= w - pad_r:
            # Map hover_x to nearest index
            total_elements = len(self.xp_data)
            index = int(round((self.hover_x - pad_l) / chart_w * (total_elements - 1)))
            index = max(0, min(index, total_elements - 1))
            
            # Retrieve values
            curr_xp = self.xp_data[index]
            curr_loot = self.loot_data[index]
            target_x = pad_l + int(chart_w * index / max(1, total_elements - 1))
            
            # Draw vertical guide line
            guide_pen = QPen(QColor(230, 126, 34), 1, Qt.PenStyle.SolidLine)
            painter.setPen(guide_pen)
            painter.drawLine(target_x, pad_t, target_x, h - pad_b)
            
            # Tooltip details bubble
            painter.fillRect(target_x - 50, pad_t + 40, 110, 45, QColor(0, 0, 0, 200))
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Arial", 8))
            painter.drawText(target_x - 45, pad_t + 55, f"XP: {curr_xp}")
            painter.drawText(target_x - 45, pad_t + 70, f"Loot: {curr_loot} items")
            
        # Text annotations
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Arial", 8))
        painter.drawText(pad_l + 10, pad_t + 15, "XP Trend (Green Line)")
        painter.drawText(pad_l + 10, pad_t + 30, "Loot Bar (Blue Bars)")


class StatisticsPage(Page):
    """Presents operational performance summaries and metrics from SQLite."""

    def __init__(self, profile_store: ProfileStore) -> None:
        super().__init__(
            "Statistics",
            "Performance metrics and operational history.",
            "Character Statistics Summary",
            "Select a profile below to load aggregated runtime stats from database storage.",
            card_eyebrow="METRICS",
        )
        self.profile_store = profile_store

        # 1. Profile selector row
        selector_layout = QHBoxLayout()
        selector_layout.setContentsMargins(0, 10, 0, 10)
        selector_label = QLabel("Select Profile:")
        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self._load_statistics)
        selector_layout.addWidget(selector_label)
        selector_layout.addWidget(self.profile_combo, 1)
        self.card_layout.addLayout(selector_layout)

        # 2. Stats summary cards layout
        self.stats_layout = QVBoxLayout()
        self.stats_layout.setSpacing(12)

        self.xp_card = QLabel("XP Accumulated: --")
        self.xp_card.setStyleSheet("font-size: 11pt; padding: 4px;")
        self.loot_card = QLabel("Total Loot Collected: --")
        self.loot_card.setStyleSheet("font-size: 11pt; padding: 4px;")
        self.deaths_card = QLabel("Character Deaths: --")
        self.deaths_card.setStyleSheet("font-size: 11pt; padding: 4px;")
        self.time_card = QLabel("Runtime: -- minutes")
        self.time_card.setStyleSheet("font-size: 11pt; padding: 4px;")

        self.stats_layout.addWidget(self.xp_card)
        self.stats_layout.addWidget(self.loot_card)
        self.stats_layout.addWidget(self.deaths_card)
        self.stats_layout.addWidget(self.time_card)

        # Add Live Performance Trend Chart widget (TASK-030)
        self.trend_chart = StatisticsTrendChart()
        self.stats_layout.addWidget(self.trend_chart)

        self.card_layout.addLayout(self.stats_layout)

        # Load list
        self._refresh_profiles()

    def _refresh_profiles(self) -> None:
        """Populate profile combobox options."""
        self.profile_combo.clear()
        profiles = self.profile_store.list_profiles()
        for p in profiles:
            self.profile_combo.addItem(p.name, p.id)

    def showEvent(self, event) -> None:
        """Refresh selection on navigation tab load."""
        super().showEvent(event)
        self._refresh_profiles()
        self._load_statistics()

    def _load_statistics(self) -> None:
        """Fetch stats for selected profile and update UI labels."""
        profile_id = self.profile_combo.currentData()
        if profile_id is None:
            self.xp_card.setText("XP Accumulated: --")
            self.loot_card.setText("Total Loot Collected: --")
            self.deaths_card.setText("Character Deaths: --")
            self.time_card.setText("Runtime: -- minutes")
            self.trend_chart.set_data([0], [0])
            return

        profile = self.profile_store.get_profile(profile_id)
        if profile and profile.stats:
            stats = profile.stats
            runtime_mins = round(stats.runtime_seconds / 60.0, 1)
            self.xp_card.setText(f"XP Accumulated: {stats.experience_gained} XP")
            self.loot_card.setText(f"Total Loot Collected: {stats.loot_count} items")
            self.deaths_card.setText(f"Character Deaths: {stats.deaths} deaths")
            self.time_card.setText(f"Runtime: {runtime_mins} minutes")
            
            # Fetch simulated trend history intervals
            simulated_xp_history = [0, int(stats.experience_gained * 0.25), int(stats.experience_gained * 0.6), stats.experience_gained]
            simulated_loot_history = [0, int(stats.loot_count * 0.3), int(stats.loot_count * 0.7), stats.loot_count]
            self.trend_chart.set_data(simulated_xp_history, simulated_loot_history)


class AboutPage(Page):
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

        # 1.5 Target Game Window Title Input row
        window_title_layout = QHBoxLayout()
        window_title_layout.setContentsMargins(0, 5, 0, 10)
        window_title_lbl = QLabel("Target Game Window Title:")
        self.window_title_input = QLineEdit()
        self.window_title_input.setPlaceholderText("e.g. Ragnarok")
        self.inject_btn = QPushButton("Inject")
        self.inject_btn.clicked.connect(self._inject_window_rename)

        window_title_layout.addWidget(window_title_lbl)
        window_title_layout.addWidget(self.window_title_input, 1)
        window_title_layout.addWidget(self.inject_btn)
        self.card_layout.addLayout(window_title_layout)

        # 2. Rule configuration Tab Widget
        self.tab_widget = QTabWidget()
        self.card_layout.addWidget(self.tab_widget)

        self._init_healing_tab()
        self._init_consumables_tab()
        self._init_looting_tab()
        self._init_combat_tab()
        self._init_navigation_tab()
        self._init_security_tab()
        self._init_stash_tab()

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

        self.heal_enabled = QCheckBox("Enable Healing & Recovery Module")
        self.heal_min_cooldown = QDoubleSpinBox()
        self.heal_min_cooldown.setRange(0.0, 10.0)
        self.heal_max_cooldown = QDoubleSpinBox()
        self.heal_max_cooldown.setRange(0.0, 10.0)

        # HP Text crop Controls
        self.heal_hp_threshold = QSpinBox()
        self.heal_hp_threshold.setRange(1, 100)
        self.heal_hp_key = QComboBox()
        self.heal_hp_key.addItems([f"F{i}" for i in range(1, 11)])

        self.heal_hp_x = QSpinBox()
        self.heal_hp_x.setRange(0, 5000)
        self.heal_hp_y = QSpinBox()
        self.heal_hp_y.setRange(0, 5000)
        self.heal_hp_w = QSpinBox()
        self.heal_hp_w.setRange(5, 500)
        self.heal_hp_w.setValue(60)
        self.heal_hp_h = QSpinBox()
        self.heal_hp_h.setRange(5, 500)
        self.heal_hp_h.setValue(12)

        # SP Text crop Controls
        self.heal_sp_enabled = QCheckBox("Enable SP (Mana) Recovery")
        self.heal_sp_threshold = QSpinBox()
        self.heal_sp_threshold.setRange(1, 100)
        self.heal_sp_key = QComboBox()
        self.heal_sp_key.addItems([f"F{i}" for i in range(1, 11)])

        self.heal_sp_x = QSpinBox()
        self.heal_sp_x.setRange(0, 5000)
        self.heal_sp_y = QSpinBox()
        self.heal_sp_y.setRange(0, 5000)
        self.heal_sp_w = QSpinBox()
        self.heal_sp_w.setRange(5, 500)
        self.heal_sp_w.setValue(60)
        self.heal_sp_h = QSpinBox()
        self.heal_sp_h.setRange(5, 500)
        self.heal_sp_h.setValue(12)

        # Build HP form section
        layout.addRow(self.heal_enabled)
        layout.addRow("HP Trigger Threshold (%)", self.heal_hp_threshold)
        layout.addRow("HP Recovery Potion Key", self.heal_hp_key)

        hp_coord_layout = QHBoxLayout()
        hp_coord_layout.addWidget(QLabel("X:"))
        hp_coord_layout.addWidget(self.heal_hp_x)
        hp_coord_layout.addWidget(QLabel("Y:"))
        hp_coord_layout.addWidget(self.heal_hp_y)
        hp_coord_layout.addWidget(QLabel("W:"))
        hp_coord_layout.addWidget(self.heal_hp_w)
        hp_coord_layout.addWidget(QLabel("H:"))
        hp_coord_layout.addWidget(self.heal_hp_h)

        self.hp_pick_btn = QPushButton("Pick HP Box")
        self.hp_pick_btn.clicked.connect(self._pick_hp_crop)
        hp_coord_layout.addWidget(self.hp_pick_btn)
        layout.addRow("HP Text Bounding Box", hp_coord_layout)

        layout.addRow(QFrame())  # Visual separator

        # Build SP form section
        layout.addRow(self.heal_sp_enabled)
        layout.addRow("SP Trigger Threshold (%)", self.heal_sp_threshold)
        layout.addRow("SP Potion Key", self.heal_sp_key)

        sp_coord_layout = QHBoxLayout()
        sp_coord_layout.addWidget(QLabel("X:"))
        sp_coord_layout.addWidget(self.heal_sp_x)
        sp_coord_layout.addWidget(QLabel("Y:"))
        sp_coord_layout.addWidget(self.heal_sp_y)
        sp_coord_layout.addWidget(QLabel("W:"))
        sp_coord_layout.addWidget(self.heal_sp_w)
        sp_coord_layout.addWidget(QLabel("H:"))
        sp_coord_layout.addWidget(self.heal_sp_h)

        self.sp_pick_btn = QPushButton("Pick SP Box")
        self.sp_pick_btn.clicked.connect(self._pick_sp_crop)
        sp_coord_layout.addWidget(self.sp_pick_btn)
        layout.addRow("SP Text Bounding Box", sp_coord_layout)

        layout.addRow(QFrame())  # Visual separator

        cd_layout = QHBoxLayout()
        cd_layout.addWidget(QLabel("Min (s):"))
        cd_layout.addWidget(self.heal_min_cooldown)
        cd_layout.addWidget(QLabel("Max (s):"))
        cd_layout.addWidget(self.heal_max_cooldown)
        layout.addRow("Action Delay Cooldowns", cd_layout)

        # Add visual verification crop button
        self.heal_verify_btn = QPushButton("📷 Verify Crop (Test OCR)")
        self.heal_verify_btn.clicked.connect(self._verify_healing_crops)
        layout.addRow("Calibration Helper", self.heal_verify_btn)

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

        self.status_bar_enabled = QCheckBox("Check Active Status Bar Icons before casting")
        layout.addWidget(self.status_bar_enabled)

        status_layout = QHBoxLayout()
        self.status_check_x = QSpinBox()
        self.status_check_x.setRange(0, 3000)
        self.status_check_x.setValue(50)
        self.status_check_y = QSpinBox()
        self.status_check_y.setRange(0, 3000)
        self.status_check_y.setValue(50)
        status_layout.addWidget(QLabel("Icon X:"))
        status_layout.addWidget(self.status_check_x)
        status_layout.addWidget(QLabel("Y:"))
        status_layout.addWidget(self.status_check_y)
        
        self.status_color_r = QSpinBox()
        self.status_color_r.setRange(0, 255)
        self.status_color_r.setValue(255)
        self.status_color_g = QSpinBox()
        self.status_color_g.setRange(0, 255)
        self.status_color_g.setValue(255)
        self.status_color_b = QSpinBox()
        self.status_color_b.setRange(0, 255)
        self.status_color_b.setValue(255)
        
        status_layout.addWidget(QLabel("R:"))
        status_layout.addWidget(self.status_color_r)
        status_layout.addWidget(QLabel("G:"))
        status_layout.addWidget(self.status_color_g)
        status_layout.addWidget(QLabel("B:"))
        status_layout.addWidget(self.status_color_b)
        
        layout.addLayout(status_layout)

        self.tab_widget.addTab(tab, "Consumables")

    def _init_looting_tab(self) -> None:
        tab = QWidget()
        layout = QFormLayout(tab)

        self.loot_enabled = QCheckBox("Enable Auto-Looting")
        self.loot_color_r = QSpinBox()
        self.loot_color_r.setRange(0, 255)
        self.loot_color_r.setValue(220)
        self.loot_color_g = QSpinBox()
        self.loot_color_g.setRange(0, 255)
        self.loot_color_g.setValue(220)
        self.loot_color_b = QSpinBox()
        self.loot_color_b.setRange(0, 255)
        self.loot_color_b.setValue(220)

        self.loot_color_tolerance = QSpinBox()
        self.loot_color_tolerance.setRange(0, 255)
        self.loot_color_tolerance.setValue(15)

        self.loot_cooldown = QDoubleSpinBox()
        self.loot_cooldown.setRange(0.0, 10.0)
        self.loot_cooldown.setValue(1.0)
        self.loot_cooldown.setSingleStep(0.1)

        layout.addRow(self.loot_enabled)

        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("R:"))
        color_layout.addWidget(self.loot_color_r)
        color_layout.addWidget(QLabel("G:"))
        color_layout.addWidget(self.loot_color_g)
        color_layout.addWidget(QLabel("B:"))
        color_layout.addWidget(self.loot_color_b)
        
        # Color picker reuse
        self.loot_pick_btn = QPushButton("Pick Loot Color")
        self.loot_pick_btn.clicked.connect(self._pick_loot_color)
        color_layout.addWidget(self.loot_pick_btn)
        
        layout.addRow("Loot Name Color (RGB)", color_layout)
        layout.addRow("Color Match Tolerance", self.loot_color_tolerance)
        layout.addRow("Looting Cooldown Delay (s)", self.loot_cooldown)

        # Rare item color filter widgets (TASK-029)
        self.loot_filter_mode = QComboBox()
        self.loot_filter_mode.addItem("Loot All Matching", "all")
        self.loot_filter_mode.addItem("Loot Rare Items Only (Red)", "rare_only")

        self.loot_rare_color_r = QSpinBox()
        self.loot_rare_color_r.setRange(0, 255)
        self.loot_rare_color_r.setValue(255)
        self.loot_rare_color_g = QSpinBox()
        self.loot_rare_color_g.setRange(0, 255)
        self.loot_rare_color_g.setValue(0)
        self.loot_rare_color_b = QSpinBox()
        self.loot_rare_color_b.setRange(0, 255)
        self.loot_rare_color_b.setValue(0)
        self.loot_rare_tolerance = QSpinBox()
        self.loot_rare_tolerance.setRange(0, 255)
        self.loot_rare_tolerance.setValue(30)

        layout.addRow("Filter Loot Mode", self.loot_filter_mode)
        
        rare_color_layout = QHBoxLayout()
        rare_color_layout.addWidget(QLabel("R:"))
        rare_color_layout.addWidget(self.loot_rare_color_r)
        rare_color_layout.addWidget(QLabel("G:"))
        rare_color_layout.addWidget(self.loot_rare_color_g)
        rare_color_layout.addWidget(QLabel("B:"))
        rare_color_layout.addWidget(self.loot_rare_color_b)
        layout.addRow("Rare Color Filter (RGB)", rare_color_layout)
        layout.addRow("Rare Tolerance", self.loot_rare_tolerance)

        self.tab_widget.addTab(tab, "Looting")

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

        # Scanning mode configurations (TASK-024)
        self.combat_scanning_mode = QComboBox()
        self.combat_scanning_mode.addItem("Color Centroid", "color")
        self.combat_scanning_mode.addItem("Monster Template Matching", "template")
        self.combat_scanning_mode.addItem("Hover HP Bar Sweep", "hover_bar")

        self.combat_template_dir = QLineEdit()
        self.combat_template_dir.setPlaceholderText("e.g. templates/monsters/")
        self.combat_template_threshold = QDoubleSpinBox()
        self.combat_template_threshold.setRange(0.1, 1.0)
        self.combat_template_threshold.setValue(0.8)
        self.combat_template_threshold.setSingleStep(0.05)

        self.combat_hover_offset_y = QSpinBox()
        self.combat_hover_offset_y.setRange(-200, 200)
        self.combat_hover_offset_y.setValue(-30)

        self.combat_hover_box_w = QSpinBox()
        self.combat_hover_box_w.setRange(5, 500)
        self.combat_hover_box_w.setValue(40)

        self.combat_hover_box_h = QSpinBox()
        self.combat_hover_box_h.setRange(2, 500)
        self.combat_hover_box_h.setValue(10)

        layout.addRow(self.combat_enabled)
        layout.addRow("Target Scanning Mode", self.combat_scanning_mode)

        # Mode options separator line
        layout.addRow(QFrame())

        # 1. Color mode layout elements
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
        layout.addRow("Color mode: RGB Target", color_layout)
        layout.addRow("Color mode: Tolerance", self.combat_color_tolerance)

        step_layout = QHBoxLayout()
        step_layout.addWidget(QLabel("Step X:"))
        step_layout.addWidget(self.combat_step_x)
        step_layout.addWidget(QLabel("Step Y:"))
        step_layout.addWidget(self.combat_step_y)
        layout.addRow("Color mode: Grid Steps", step_layout)
        layout.addRow("Color mode: Min Hits", self.combat_min_hits)

        # 2. Template matching mode elements
        self.combat_priority_enabled = QCheckBox("Enable Target Priorities (high/low priority subdirs)")
        layout.addRow("Template mode: Priority Sorting", self.combat_priority_enabled)
        layout.addRow("Template mode: Directory", self.combat_template_dir)
        layout.addRow("Template mode: Threshold", self.combat_template_threshold)

        # 3. Hover HP bar mode elements
        hover_size_layout = QHBoxLayout()
        hover_size_layout.addWidget(QLabel("Offset Y:"))
        hover_size_layout.addWidget(self.combat_hover_offset_y)
        hover_size_layout.addWidget(QLabel("Box W:"))
        hover_size_layout.addWidget(self.combat_hover_box_w)
        hover_size_layout.addWidget(QLabel("Box H:"))
        hover_size_layout.addWidget(self.combat_hover_box_h)
        layout.addRow("Hover mode: Check Box Sizes", hover_size_layout)

        # Separator line
        layout.addRow(QFrame())

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

        # Transition Settings Row (TASK-030)
        self.nav_transition_enabled = QCheckBox("Enable Multi-Map Portal Transitions")
        layout.addWidget(self.nav_transition_enabled)

        trans_layout = QFormLayout()
        self.nav_current_map = QLineEdit()
        self.nav_current_map.setText("prt_fild08")
        self.nav_current_map.setPlaceholderText("Current map name")
        
        self.nav_target_map = QLineEdit()
        self.nav_target_map.setText("prt_fild08")
        self.nav_target_map.setPlaceholderText("Target map name")

        self.nav_transitions_text = QTextEdit()
        self.nav_transitions_text.setPlaceholderText("Format: from:to:x:y:wait;...")
        self.nav_transitions_text.setMaximumHeight(80)

        trans_layout.addRow("Current Map Name", self.nav_current_map)
        trans_layout.addRow("Target Map Name", self.nav_target_map)
        trans_layout.addRow("Map Portal Coordinates Gates", self.nav_transitions_text)
        layout.addLayout(trans_layout)

        self.tab_widget.addTab(tab, "Navigation")

    def _init_security_tab(self) -> None:
        tab = QWidget()
        layout = QFormLayout(tab)

        self.sec_enabled = QCheckBox("Enable Anti-Detection & Captcha Scanner")
        self.sec_templates_dir = QLineEdit()
        self.sec_templates_dir.setPlaceholderText("e.g. templates/security/")
        
        self.sec_threshold = QDoubleSpinBox()
        self.sec_threshold.setRange(0.1, 1.0)
        self.sec_threshold.setValue(0.85)
        self.sec_threshold.setSingleStep(0.05)

        self.sec_panic_action = QComboBox()
        self.sec_panic_action.addItem("Only Audio/Visual Alarm Notification", "alarm_only")
        self.sec_panic_action.addItem("Press Teleport Hotkey", "teleport")
        self.sec_panic_action.addItem("Force Quit Client (ALT+F4)", "logout")

        self.sec_panic_hotkey = QLineEdit()
        self.sec_panic_hotkey.setText("F12")
        self.sec_panic_hotkey.setPlaceholderText("e.g. F12")

        self.sec_discord_webhook = QLineEdit()
        self.sec_discord_webhook.setPlaceholderText("e.g. https://discord.com/api/webhooks/...")

        layout.addRow(self.sec_enabled)
        layout.addRow("Captcha Templates Directory", self.sec_templates_dir)
        layout.addRow("Detection Threshold", self.sec_threshold)
        layout.addRow("Panic Action Response", self.sec_panic_action)
        layout.addRow("Teleport Panic Hotkey", self.sec_panic_hotkey)
        layout.addRow("Discord Webhook URL", self.sec_discord_webhook)

        self.tab_widget.addTab(tab, "Security")

    def _init_stash_tab(self) -> None:
        tab = QWidget()
        layout = QFormLayout(tab)

        self.stash_enabled = QCheckBox("Enable Auto-Stash Kafra Banking")
        self.stash_teleport_hotkey = QLineEdit()
        self.stash_teleport_hotkey.setText("F12")
        self.stash_teleport_hotkey.setPlaceholderText("e.g. F12")

        self.stash_kafra_x = QSpinBox()
        self.stash_kafra_x.setRange(0, 3000)
        self.stash_kafra_x.setValue(300)

        self.stash_kafra_y = QSpinBox()
        self.stash_kafra_y.setRange(0, 3000)
        self.stash_kafra_y.setValue(300)

        self.stash_weight_check_x = QSpinBox()
        self.stash_weight_check_x.setRange(0, 3000)
        self.stash_weight_check_x.setValue(600)
        self.stash_weight_check_y = QSpinBox()
        self.stash_weight_check_y.setRange(0, 3000)
        self.stash_weight_check_y.setValue(50)

        # Restock rules widgets (TASK-028)
        self.stash_restock_enabled = QCheckBox("Enable Potion/Fly Wing Merchant Restocking")
        
        self.stash_merchant_x = QSpinBox()
        self.stash_merchant_x.setRange(0, 3000)
        self.stash_merchant_x.setValue(400)

        self.stash_merchant_y = QSpinBox()
        self.stash_merchant_y.setRange(0, 3000)
        self.stash_merchant_y.setValue(400)

        layout.addRow(self.stash_enabled)
        layout.addRow("Town Teleport Hotkey", self.stash_teleport_hotkey)
        
        kafra_coords = QHBoxLayout()
        kafra_coords.addWidget(QLabel("X:"))
        kafra_coords.addWidget(self.stash_kafra_x)
        kafra_coords.addWidget(QLabel("Y:"))
        kafra_coords.addWidget(self.stash_kafra_y)
        layout.addRow("Kafra NPC Coordinates", kafra_coords)

        weight_coords = QHBoxLayout()
        weight_coords.addWidget(QLabel("X:"))
        weight_coords.addWidget(self.stash_weight_check_x)
        weight_coords.addWidget(QLabel("Y:"))
        weight_coords.addWidget(self.stash_weight_check_y)
        layout.addRow("Weight Warning Icon Pixel Coords", weight_coords)

        # restock row
        layout.addRow(self.stash_restock_enabled)
        merchant_coords = QHBoxLayout()
        merchant_coords.addWidget(QLabel("X:"))
        merchant_coords.addWidget(self.stash_merchant_x)
        merchant_coords.addWidget(QLabel("Y:"))
        merchant_coords.addWidget(self.stash_merchant_y)
        layout.addRow("Merchant NPC Coordinates", merchant_coords)

        # NPC Selling row (TASK-032)
        self.stash_sell_enabled = QCheckBox("Enable NPC Junk Item Selling")
        self.stash_sell_npc_x = QSpinBox()
        self.stash_sell_npc_x.setRange(0, 3000)
        self.stash_sell_npc_x.setValue(500)
        
        self.stash_sell_npc_y = QSpinBox()
        self.stash_sell_npc_y.setRange(0, 3000)
        self.stash_sell_npc_y.setValue(500)

        layout.addRow(self.stash_sell_enabled)
        sell_coords = QHBoxLayout()
        sell_coords.addWidget(QLabel("X:"))
        sell_coords.addWidget(self.stash_sell_npc_x)
        sell_coords.addWidget(QLabel("Y:"))
        sell_coords.addWidget(self.stash_sell_npc_y)
        layout.addRow("Sell NPC Store Coordinates", sell_coords)

        self.tab_widget.addTab(tab, "Stash")

    def _load_profile_rules(self) -> None:
        """Populate rule form fields with values from database or fallbacks to defaults."""
        profile_id = self.profile_combo.currentData()
        if profile_id is None:
            return

        profile = self.profile_store.get_profile(profile_id)
        if not profile:
            return

        # Load metadata
        self.window_title_input.setText(profile.window_title or "")

        rules = profile.rules

        # Load Healing rules
        heal = rules.get("healing", {})
        self.heal_enabled.setChecked(heal.get("heal.enabled", "false").lower() == "true")
        self.heal_hp_threshold.setValue(int(heal.get("heal.hp_threshold", "70")))
        self.heal_hp_key.setCurrentText(heal.get("heal.hp_key", "F1"))

        self.heal_hp_x.setValue(int(heal.get("heal.hp_x", "100")))
        self.heal_hp_y.setValue(int(heal.get("heal.hp_y", "50")))
        self.heal_hp_w.setValue(int(heal.get("heal.hp_w", "60")))
        self.heal_hp_h.setValue(int(heal.get("heal.hp_h", "12")))

        self.heal_sp_enabled.setChecked(heal.get("heal.sp_enabled", "false").lower() == "true")
        self.heal_sp_threshold.setValue(int(heal.get("heal.sp_threshold", "50")))
        self.heal_sp_key.setCurrentText(heal.get("heal.sp_key", "F2"))

        self.heal_sp_x.setValue(int(heal.get("heal.sp_x", "100")))
        self.heal_sp_y.setValue(int(heal.get("heal.sp_y", "66")))
        self.heal_sp_w.setValue(int(heal.get("heal.sp_w", "60")))
        self.heal_sp_h.setValue(int(heal.get("heal.sp_h", "12")))

        self.heal_min_cooldown.setValue(float(heal.get("heal.min_cooldown", "0.5")))
        self.heal_max_cooldown.setValue(float(heal.get("heal.max_cooldown", "0.8")))

        # Load Consumables rules
        cons = rules.get("consumables", {})
        self.consumables_enabled.setChecked(
            cons.get("consumables.enabled", "false").lower() == "true"
        )
        self.consumables_text.setPlainText(cons.get("consumables.items", ""))
        self.status_bar_enabled.setChecked(cons.get("consumables.status_bar_enabled", "false").lower() == "true")
        self.status_check_x.setValue(int(cons.get("consumables.status_check_x", "50")))
        self.status_check_y.setValue(int(cons.get("consumables.status_check_y", "50")))
        self.status_color_r.setValue(int(cons.get("consumables.status_color_r", "255")))
        self.status_color_g.setValue(int(cons.get("consumables.status_color_g", "255")))
        self.status_color_b.setValue(int(cons.get("consumables.status_color_b", "255")))

        # Load Looting rules
        loot = rules.get("looting", {})
        self.loot_enabled.setChecked(loot.get("loot.enabled", "false").lower() == "true")
        self.loot_color_r.setValue(int(loot.get("loot.color.r", "220")))
        self.loot_color_g.setValue(int(loot.get("loot.color.g", "220")))
        self.loot_color_b.setValue(int(loot.get("loot.color.b", "220")))
        self.loot_color_tolerance.setValue(int(loot.get("loot.color.tolerance", "15")))
        self.loot_cooldown.setValue(float(loot.get("loot.cooldown", "1.0")))
        
        filt_idx = self.loot_filter_mode.findData(loot.get("loot.filter_mode", "all"))
        if filt_idx >= 0:
            self.loot_filter_mode.setCurrentIndex(filt_idx)
        self.loot_rare_color_r.setValue(int(loot.get("loot.rare_color.r", "255")))
        self.loot_rare_color_g.setValue(int(loot.get("loot.rare_color.g", "0")))
        self.loot_rare_color_b.setValue(int(loot.get("loot.rare_color.b", "0")))
        self.loot_rare_tolerance.setValue(int(loot.get("loot.rare_tolerance", "30")))

        # Load Combat rules
        combat = rules.get("combat", {})
        self.combat_enabled.setChecked(combat.get("combat.enabled", "false").lower() == "true")
        
        # Load combobox index based on string values
        curr_mode = combat.get("combat.scanning_mode", "color")
        idx = self.combat_scanning_mode.findData(curr_mode)
        if idx >= 0:
            self.combat_scanning_mode.setCurrentIndex(idx)

        self.combat_target_r.setValue(int(combat.get("combat.target_r", "255")))
        self.combat_target_g.setValue(int(combat.get("combat.target_g", "0")))
        self.combat_target_b.setValue(int(combat.get("combat.target_b", "0")))
        self.combat_color_tolerance.setValue(int(combat.get("combat.color_tolerance", "30")))
        self.combat_step_x.setValue(int(combat.get("combat.step_x", "5")))
        self.combat_step_y.setValue(int(combat.get("combat.step_y", "5")))
        self.combat_min_hits.setValue(int(combat.get("combat.min_hits", "3")))
        self.combat_min_cooldown.setValue(float(combat.get("combat.min_cooldown", "1.0")))
        self.combat_max_cooldown.setValue(float(combat.get("combat.max_cooldown", "2.0")))

        self.combat_template_dir.setText(combat.get("combat.template_dir", ""))
        self.combat_template_threshold.setValue(float(combat.get("combat.template_threshold", "0.8")))
        self.combat_priority_enabled.setChecked(combat.get("combat.priority_enabled", "false").lower() == "true")
        self.combat_hover_offset_y.setValue(int(combat.get("combat.hover_offset_y", "-30")))
        self.combat_hover_box_w.setValue(int(combat.get("combat.hover_box_w", "40")))
        self.combat_hover_box_h.setValue(int(combat.get("combat.hover_box_h", "10")))

        # Load Navigation rules
        nav = rules.get("navigation", {})
        self.nav_enabled.setChecked(nav.get("navigation.enabled", "false").lower() == "true")
        self.nav_waypoints_text.setPlainText(nav.get("navigation.waypoints", ""))
        self.nav_map_file_str = nav.get("navigation.map_file", "")
        
        # Load transition configs (TASK-030)
        self.nav_transition_enabled.setChecked(nav.get("navigation.transition_enabled", "false").lower() == "true")
        self.nav_current_map.setText(nav.get("navigation.current_map", "prt_fild08"))
        self.nav_target_map.setText(nav.get("navigation.target_map", "prt_fild08"))
        self.nav_transitions_text.setPlainText(nav.get("navigation.transitions", ""))

        # Load Security rules (TASK-025)
        sec = rules.get("security", {})
        self.sec_enabled.setChecked(sec.get("security.enabled", "false").lower() == "true")
        self.sec_templates_dir.setText(sec.get("security.templates_dir", ""))
        self.sec_threshold.setValue(float(sec.get("security.threshold", "0.85")))
        
        sec_idx = self.sec_panic_action.findData(sec.get("security.panic_action", "alarm_only"))
        if sec_idx >= 0:
            self.sec_panic_action.setCurrentIndex(sec_idx)
        self.sec_panic_hotkey.setText(sec.get("security.panic_hotkey", "F12"))
        self.sec_discord_webhook.setText(sec.get("security.discord_webhook", ""))

        # Load Stash rules (TASK-027)
        stash = rules.get("stash", {})
        self.stash_enabled.setChecked(stash.get("stash.enabled", "false").lower() == "true")
        self.stash_teleport_hotkey.setText(stash.get("stash.teleport_hotkey", "F12"))
        self.stash_kafra_x.setValue(int(stash.get("stash.kafra_x", "300")))
        self.stash_kafra_y.setValue(int(stash.get("stash.kafra_y", "300")))
        self.stash_weight_check_x.setValue(int(stash.get("stash.weight_check_x", "600")))
        self.stash_weight_check_y.setValue(int(stash.get("stash.weight_check_y", "50")))
        
        # Load restock rules (TASK-028)
        self.stash_restock_enabled.setChecked(stash.get("stash.restock_enabled", "false").lower() == "true")
        self.stash_merchant_x.setValue(int(stash.get("stash.merchant_x", "400")))
        self.stash_merchant_y.setValue(int(stash.get("stash.merchant_y", "400")))

        # Load selling rules (TASK-032)
        self.stash_sell_enabled.setChecked(stash.get("stash.sell_enabled", "false").lower() == "true")
        self.stash_sell_npc_x.setValue(int(stash.get("stash.sell_npc_x", "500")))
        self.stash_sell_npc_y.setValue(int(stash.get("stash.sell_npc_y", "500")))

    def _save_profile_rules(self) -> None:
        """Persist rule configuration fields to the SQLite profile database."""
        profile_id = self.profile_combo.currentData()
        if profile_id is None:
            QMessageBox.warning(self, "No Profile", "Create or select a profile first.")
            return

        try:
            # 0. Save window title metadata
            window_title = self.window_title_input.text().strip()
            self.profile_store.update_profile_window_title(profile_id, window_title)

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
                profile_id, "healing", "heal.hp_w", str(self.heal_hp_w.value())
            )
            self.profile_store.set_rule(
                profile_id, "healing", "heal.hp_h", str(self.heal_hp_h.value())
            )

            # Save SP Rules
            self.profile_store.set_rule(
                profile_id,
                "healing",
                "heal.sp_enabled",
                str(self.heal_sp_enabled.isChecked()).lower(),
            )
            self.profile_store.set_rule(
                profile_id, "healing", "heal.sp_threshold", str(self.heal_sp_threshold.value())
            )
            self.profile_store.set_rule(
                profile_id, "healing", "heal.sp_key", self.heal_sp_key.currentText()
            )
            self.profile_store.set_rule(
                profile_id, "healing", "heal.sp_x", str(self.heal_sp_x.value())
            )
            self.profile_store.set_rule(
                profile_id, "healing", "heal.sp_y", str(self.heal_sp_y.value())
            )
            self.profile_store.set_rule(
                profile_id, "healing", "heal.sp_w", str(self.heal_sp_w.value())
            )
            self.profile_store.set_rule(
                profile_id, "healing", "heal.sp_h", str(self.heal_sp_h.value())
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
            self.profile_store.set_rule(
                profile_id,
                "consumables",
                "consumables.status_bar_enabled",
                str(self.status_bar_enabled.isChecked()).lower(),
            )
            self.profile_store.set_rule(
                profile_id,
                "consumables",
                "consumables.status_check_x",
                str(self.status_check_x.value()),
            )
            self.profile_store.set_rule(
                profile_id,
                "consumables",
                "consumables.status_check_y",
                str(self.status_check_y.value()),
            )
            self.profile_store.set_rule(
                profile_id,
                "consumables",
                "consumables.status_color_r",
                str(self.status_color_r.value()),
            )
            self.profile_store.set_rule(
                profile_id,
                "consumables",
                "consumables.status_color_g",
                str(self.status_color_g.value()),
            )
            self.profile_store.set_rule(
                profile_id,
                "consumables",
                "consumables.status_color_b",
                str(self.status_color_b.value()),
            )

            # Save Looting rules
            self.profile_store.set_rule(
                profile_id, "looting", "loot.enabled", str(self.loot_enabled.isChecked()).lower()
            )
            self.profile_store.set_rule(
                profile_id, "looting", "loot.color.r", str(self.loot_color_r.value())
            )
            self.profile_store.set_rule(
                profile_id, "looting", "loot.color.g", str(self.loot_color_g.value())
            )
            self.profile_store.set_rule(
                profile_id, "looting", "loot.color.b", str(self.loot_color_b.value())
            )
            self.profile_store.set_rule(
                profile_id, "looting", "loot.color.tolerance", str(self.loot_color_tolerance.value())
            )
            self.profile_store.set_rule(
                profile_id, "looting", "loot.cooldown", str(self.loot_cooldown.value())
            )
            self.profile_store.set_rule(
                profile_id, "looting", "loot.filter_mode", self.loot_filter_mode.currentData()
            )
            self.profile_store.set_rule(
                profile_id, "looting", "loot.rare_color.r", str(self.loot_rare_color_r.value())
            )
            self.profile_store.set_rule(
                profile_id, "looting", "loot.rare_color.g", str(self.loot_rare_color_g.value())
            )
            self.profile_store.set_rule(
                profile_id, "looting", "loot.rare_color.b", str(self.loot_rare_color_b.value())
            )
            self.profile_store.set_rule(
                profile_id, "looting", "loot.rare_tolerance", str(self.loot_rare_tolerance.value())
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
            
            # Save OpenCV configurations (TASK-024)
            self.profile_store.set_rule(
                profile_id, "combat", "combat.scanning_mode", self.combat_scanning_mode.currentData()
            )
            self.profile_store.set_rule(
                profile_id, "combat", "combat.template_dir", self.combat_template_dir.text().strip()
            )
            self.profile_store.set_rule(
                profile_id, "combat", "combat.template_threshold", str(self.combat_template_threshold.value())
            )
            self.profile_store.set_rule(
                profile_id, "combat", "combat.priority_enabled", str(self.combat_priority_enabled.isChecked()).lower()
            )
            self.profile_store.set_rule(
                profile_id, "combat", "combat.hover_offset_y", str(self.combat_hover_offset_y.value())
            )
            self.profile_store.set_rule(
                profile_id, "combat", "combat.hover_box_w", str(self.combat_hover_box_w.value())
            )
            self.profile_store.set_rule(
                profile_id, "combat", "combat.hover_box_h", str(self.combat_hover_box_h.value())
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
            # Directly persist navigation.map_file string setting (TASK-026)
            self.profile_store.set_rule(
                profile_id,
                "navigation",
                "navigation.map_file",
                getattr(self, "nav_map_file_str", "")
            )
            
            # Save transition configs (TASK-030)
            self.profile_store.set_rule(
                profile_id,
                "navigation",
                "navigation.transition_enabled",
                str(self.nav_transition_enabled.isChecked()).lower(),
            )
            self.profile_store.set_rule(
                profile_id,
                "navigation",
                "navigation.current_map",
                self.nav_current_map.text().strip(),
            )
            self.profile_store.set_rule(
                profile_id,
                "navigation",
                "navigation.target_map",
                self.nav_target_map.text().strip(),
            )
            self.profile_store.set_rule(
                profile_id,
                "navigation",
                "navigation.transitions",
                self.nav_transitions_text.toPlainText().strip(),
            )

            # Save Security rules (TASK-025)
            self.profile_store.set_rule(
                profile_id, "security", "security.enabled", str(self.sec_enabled.isChecked()).lower()
            )
            self.profile_store.set_rule(
                profile_id, "security", "security.templates_dir", self.sec_templates_dir.text().strip()
            )
            self.profile_store.set_rule(
                profile_id, "security", "security.threshold", str(self.sec_threshold.value())
            )
            self.profile_store.set_rule(
                profile_id, "security", "security.panic_action", self.sec_panic_action.currentData()
            )
            self.profile_store.set_rule(
                profile_id, "security", "security.panic_hotkey", self.sec_panic_hotkey.text().strip()
            )
            self.profile_store.set_rule(
                profile_id, "security", "security.discord_webhook", self.sec_discord_webhook.text().strip()
            )

            # Save Stash rules (TASK-027)
            self.profile_store.set_rule(
                profile_id, "stash", "stash.enabled", str(self.stash_enabled.isChecked()).lower()
            )
            self.profile_store.set_rule(
                profile_id, "stash", "stash.teleport_hotkey", self.stash_teleport_hotkey.text().strip()
            )
            self.profile_store.set_rule(
                profile_id, "stash", "stash.kafra_x", str(self.stash_kafra_x.value())
            )
            self.profile_store.set_rule(
                profile_id, "stash", "stash.kafra_y", str(self.stash_kafra_y.value())
            )
            self.profile_store.set_rule(
                profile_id, "stash", "stash.weight_check_x", str(self.stash_weight_check_x.value())
            )
            self.profile_store.set_rule(
                profile_id, "stash", "stash.weight_check_y", str(self.stash_weight_check_y.value())
            )
            
            # Save restock options (TASK-028)
            self.profile_store.set_rule(
                profile_id, "stash", "stash.restock_enabled", str(self.stash_restock_enabled.isChecked()).lower()
            )
            self.profile_store.set_rule(
                profile_id, "stash", "stash.merchant_x", str(self.stash_merchant_x.value())
            )
            self.profile_store.set_rule(
                profile_id, "stash", "stash.merchant_y", str(self.stash_merchant_y.value())
            )

            # Save NPC Selling rules (TASK-032)
            self.profile_store.set_rule(
                profile_id, "stash", "stash.sell_enabled", str(self.stash_sell_enabled.isChecked()).lower()
            )
            self.profile_store.set_rule(
                profile_id, "stash", "stash.sell_npc_x", str(self.stash_sell_npc_x.value())
            )
            self.profile_store.set_rule(
                profile_id, "stash", "stash.sell_npc_y", str(self.stash_sell_npc_y.value())
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

    def _pick_hp_crop(self) -> None:
        """Capture the top-left coordinate of the HP text bounding box."""
        pixmap = self._capture_game_window()
        if pixmap is None:
            return
        dialog = PickDialog(pixmap, self)
        if dialog.exec() == QDialog.Accepted:
            if dialog.selected_x is not None:
                self.heal_hp_x.setValue(dialog.selected_x)
                self.heal_hp_y.setValue(dialog.selected_y)

    def _pick_sp_crop(self) -> None:
        """Capture the top-left coordinate of the SP text bounding box."""
        pixmap = self._capture_game_window()
        if pixmap is None:
            return
        dialog = PickDialog(pixmap, self)
        if dialog.exec() == QDialog.Accepted:
            if dialog.selected_x is not None:
                self.heal_sp_x.setValue(dialog.selected_x)
                self.heal_sp_y.setValue(dialog.selected_y)

    def _verify_healing_crops(self) -> None:
        """Capture the current frame, crop HP/SP bounding boxes, parse them with OCR, and show visual dialog."""
        pixmap = self._capture_game_window()
        if pixmap is None:
            return

        # Convert QPixmap to PIL image
        qimg = pixmap.toImage()
        qimg = qimg.convertToFormat(QImage.Format.Format_RGBA8888)
        img_w, img_h = qimg.width(), qimg.height()
        
        # Read raw image pointer bytes using PySide memory buffer parsing
        ptr = qimg.constBits()
        img_bytes = ptr.tobytes()
        pil_img = Image.frombytes("RGBA", (img_w, img_h), img_bytes)

        # 1. HP Crop Processing
        hp_x, hp_y = self.heal_hp_x.value(), self.heal_hp_y.value()
        hp_w, hp_h = self.heal_hp_w.value(), self.heal_hp_h.value()
        hp_x2 = min(hp_x + hp_w, img_w)
        hp_y2 = min(hp_y + hp_h, img_h)
        hp_crop = pil_img.crop((hp_x, hp_y, hp_x2, hp_y2))

        # 2. SP Crop Processing
        sp_x, sp_y = self.heal_sp_x.value(), self.heal_sp_y.value()
        sp_w, sp_h = self.heal_sp_w.value(), self.heal_sp_h.value()
        sp_x2 = min(sp_x + sp_w, img_w)
        sp_y2 = min(sp_y + sp_h, img_h)
        sp_crop = pil_img.crop((sp_x, sp_y, sp_x2, sp_y2))

        # Parse through DigitRecognizer
        from midgard.vision.ocr import DigitRecognizer
        recognizer = DigitRecognizer()
        
        hp_text = recognizer.parse_image(hp_crop)
        hp_cur, hp_max = recognizer.extract_percentage_or_values(hp_crop)
        hp_pct = (hp_cur / hp_max * 100.0) if hp_max > 0 else 0.0

        sp_text = recognizer.parse_image(sp_crop)
        sp_cur, sp_max = recognizer.extract_percentage_or_values(sp_crop)
        sp_pct = (sp_cur / sp_max * 100.0) if sp_max > 0 else 0.0

        # Construct visual modal dialog to display result
        dialog = QDialog(self)
        dialog.setWindowTitle("Verify Crop & OCR Output")
        dialog.setMinimumWidth(320)
        diag_layout = QVBoxLayout(dialog)

        # Helper method to convert PIL to QPixmap
        def pil_to_pixmap(pil_c):
            c_img = pil_c.convert("RGBA")
            c_data = c_img.tobytes("raw", "RGBA")
            pc_w, pc_h = pil_c.size
            q_char = QImage(c_data, pc_w, pc_h, QImage.Format.Format_RGBA8888)
            # Scale up for easy user inspection
            scaled = QPixmap.fromImage(q_char).scaled(
                pc_w * 3, pc_h * 3, Qt.AspectRatioMode.KeepAspectRatio
            )
            return scaled

        # HP visual block
        hp_label = QLabel("<b>HP Crop Crop Area (Scaled x3):</b>")
        hp_img_lbl = QLabel()
        hp_img_lbl.setPixmap(pil_to_pixmap(hp_crop))
        hp_res_lbl = QLabel(f"OCR String: <b>'{hp_text}'</b> &rarr; Calculated: <b>{hp_cur}/{hp_max} ({hp_pct:.1f}%)</b>")
        
        diag_layout.addWidget(hp_label)
        diag_layout.addWidget(hp_img_lbl)
        diag_layout.addWidget(hp_res_lbl)

        # SP visual block
        sp_label = QLabel("<br><b>SP Crop Crop Area (Scaled x3):</b>")
        sp_img_lbl = QLabel()
        sp_img_lbl.setPixmap(pil_to_pixmap(sp_crop))
        sp_res_lbl = QLabel(f"OCR String: <b>'{sp_text}'</b> &rarr; Calculated: <b>{sp_cur}/{sp_max} ({sp_pct:.1f}%)</b>")

        diag_layout.addWidget(sp_label)
        diag_layout.addWidget(sp_img_lbl)
        diag_layout.addWidget(sp_res_lbl)

        from PySide6.QtWidgets import QDialogButtonBox
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(dialog.accept)
        diag_layout.addWidget(buttons)

        dialog.exec()

    def _pick_loot_color(self) -> None:
        """Show color picker to capture loot name plate colors."""
        pixmap = self._capture_game_window()
        if pixmap is None:
            return
        dialog = PickDialog(pixmap, self)
        if dialog.exec() == QDialog.Accepted:
            if dialog.selected_r is not None:
                self.loot_color_r.setValue(dialog.selected_r)
                self.loot_color_g.setValue(dialog.selected_g)
                self.loot_color_b.setValue(dialog.selected_b)

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

    def _inject_window_rename(self) -> None:
        """Find windows by title prefix, and bind selected process ID (PID) to profile."""
        search_query = self.window_title_input.text().strip()
        # Fallback to search query parser in case of existing "Ragnarok [PID: 123]" string
        if " [pid: " in search_query.lower():
            search_query = search_query.lower().split(" [pid: ")[0].strip()

        if not search_query:
            QMessageBox.warning(self, "Empty Query", "Please type a window title prefix to search.")
            return

        profile_id = self.profile_combo.currentData()
        if profile_id is None:
            QMessageBox.warning(self, "No Profile", "Create or select a profile first.")
            return

        profile = self.profile_store.get_profile(profile_id)
        if not profile:
            return

        # Find matching window handles with their respective process IDs (PIDs)
        windows = list_windows_by_title_with_pid(search_query)
        if not windows:
            QMessageBox.warning(
                self, "Not Found", f"No open windows found matching: '{search_query}'"
            )
            return

        # Trigger selection Dialog
        dialog = WindowListDialog(windows, self)
        if dialog.exec() == QDialog.Accepted and dialog.selected_hwnd is not None:
            # Bind character profile directly using the format "WindowName [PID: 1234]"
            new_title = f"{search_query} [PID: {dialog.selected_pid}]"
            self.window_title_input.setText(new_title)
            # Persist directly in SQLite
            self.profile_store.update_profile_window_title(profile_id, new_title)
            QMessageBox.information(
                self,
                "Success",
                f"Successfully injected profile '{profile.name}'!\n"
                f"Bound to Window PID: {dialog.selected_pid}",
            )
