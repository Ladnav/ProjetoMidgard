import time
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
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
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

    #: Telemetry arrives ~20x/second; persist and chart at most one sample/second.
    SAMPLE_INTERVAL_SECONDS = 1.0

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
        self._last_sample_time = 0.0

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

        # 3. Telemetry cards
        tele_layout = QHBoxLayout()
        tele_layout.setSpacing(10)
        self.status_card = StatCard("Status", "Idle")
        self.xp_card = StatCard("XP Gained", "0")
        self.loot_card = StatCard("Loot", "0")
        self.hp_card = StatCard("HP", "--%")

        # Health bar lives inside the HP card, under its numeric value.
        self.hp_bar = QProgressBar()
        self.hp_bar.setObjectName("hpBar")
        self.hp_bar.setRange(0, 100)
        self.hp_bar.setValue(0)
        self.hp_bar.setTextVisible(False)
        self.hp_card.layout().addWidget(self.hp_bar)

        for card in (self.status_card, self.xp_card, self.loot_card, self.hp_card):
            tele_layout.addWidget(card, 1)
        self.card_layout.addLayout(tele_layout)

        # Backwards-compatible aliases: existing callers and tests address these
        # labels directly, so keep them pointing at the card value labels.
        self.status_lbl = self.status_card.value_label
        self.xp_lbl = self.xp_card.value_label
        self.loot_lbl = self.loot_card.value_label
        self.hp_lbl = self.hp_card.value_label

        # 4. Live performance trend chart (fed by real telemetry samples)
        self.live_chart = StatisticsTrendChart()
        self.card_layout.addWidget(self.live_chart)

        # 5. Live log terminal styling
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        # Styled through the theme stylesheet so the console follows light/dark
        # instead of being pinned to one hardcoded palette.
        self.terminal.setObjectName("console")
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

            self.status_card.set_value("Starting...")
            self.terminal.clear()
            self.live_chart.reset_live()
            self._last_sample_time = 0.0
            # The engine restarts its XP/loot counters from zero each run, so
            # keeping the previous session's samples would render a meaningless
            # sawtooth. Start the recorded series fresh for this session.
            try:
                self.profile_store.clear_stat_samples(profile_id)
            except Exception:
                pass
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
                self.status_card.set_value("Paused")
            else:
                self.launcher.send_command("start")
                self.pause_btn.setText("Pause")
                self.status_card.set_value("Running")

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
                self.status_card.set_value("Running")

        prefix = f"[{level}] " if level else ""
        self.terminal.append(f"{prefix}{message}")

    def _on_status_received(self, status: dict) -> None:
        hp = status.get("hp_pct", 100)
        xp = status.get("xp_gained", 0)
        loot = status.get("loot_collected", 0)

        hp_value = max(0, min(100, int(hp)))
        self.hp_card.set_value(f"{hp}%", alert=hp_value < 30)
        self.xp_card.set_value(f"{xp:,}")
        self.loot_card.set_value(f"{loot:,}")

        self.hp_bar.setValue(hp_value)
        # Drive the bar colour through a dynamic property so the palette stays in
        # the theme stylesheet instead of hardcoded widget-level colours.
        level = "low" if hp_value < 30 else ("mid" if hp_value < 60 else "ok")
        if self.hp_bar.property("level") != level:
            self.hp_bar.setProperty("level", level)
            _repolish(self.hp_bar)

        # The engine emits status roughly 20x per second. Sampling the chart and
        # the database at that rate would store ~72k rows per hour and reduce the
        # live chart to a few seconds of history, so throttle the persistence to
        # one sample per second while the labels keep updating in real time.
        now = time.monotonic()
        if now - self._last_sample_time < self.SAMPLE_INTERVAL_SECONDS:
            return
        elapsed = now - self._last_sample_time if self._last_sample_time else 0.0
        self._last_sample_time = now

        # Feed the live trend chart with the real telemetry point.
        self.live_chart.append_sample(xp, loot)

        # Persist dynamic stats incrementally inside SQLite
        profile_id = self.profile_combo.currentData()
        if profile_id is not None:
            try:
                profile = self.profile_store.get_profile(profile_id)
                deaths = profile.stats.deaths if (profile and profile.stats) else 0
                previous_runtime = (
                    profile.stats.runtime_seconds if (profile and profile.stats) else 0.0
                )
                # Accumulate the real elapsed wall time. The previous code added a
                # flat 1.0 per telemetry message, which overstated runtime ~20x.
                self.profile_store.update_stats(
                    profile_id=profile_id,
                    experience_gained=xp,
                    deaths=deaths,
                    loot_count=loot,
                    runtime_seconds=previous_runtime + elapsed,
                )
                # Record a time-series sample so the Statistics page can render a
                # real historical trend across the session.
                self.profile_store.add_stat_sample(
                    profile_id=profile_id,
                    experience_gained=xp,
                    loot_count=loot,
                    hp_pct=int(hp),
                )
            except Exception:
                pass

    def _on_worker_finished(self) -> None:
        self.status_card.set_value("Stopped")
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
        if alarm_type == "death":
            self.status_card.set_value("Death detected", alert=True)
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
            self.status_card.set_value("Disconnected", alert=True)
        elif alarm_type == "template_match":
            self.status_card.set_value("Visual state", alert=True)

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
        # Theme-driven console styling (see theme.stylesheet).
        self.log_viewer.setObjectName("console")
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


def _format_compact(value: float) -> str:
    """Compact numeric formatting: 1500 -> '1.5k', 2_000_000 -> '2.0M'."""
    abs_v = abs(value)
    if abs_v >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs_v >= 1_000:
        return f"{value / 1_000:.1f}k"
    return f"{int(value)}"


def _repolish(widget) -> None:
    """Re-apply the stylesheet after a widget's object name or property changed."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _format_duration(seconds: float) -> str:
    """Render a duration compactly, e.g. '45s', '12m 30s', '3h 05m'."""
    total = int(max(0, seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


class StatCard(QFrame):
    """Compact metric tile showing a large value above a small caption."""

    def __init__(self, caption: str, value: str = "--") -> None:
        super().__init__()
        self.setObjectName("statCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(2)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("statValue")
        self.caption_label = QLabel(caption.upper())
        self.caption_label.setObjectName("statCaption")

        layout.addWidget(self.value_label)
        layout.addWidget(self.caption_label)

    def set_value(self, value: str, alert: bool = False) -> None:
        """Update the displayed value, optionally styling it as an alert."""
        self.value_label.setText(value)
        self.value_label.setObjectName("statValueAlert" if alert else "statValue")
        # Re-polish so the freshly assigned object name picks up the stylesheet.
        _repolish(self.value_label)


class StatisticsTrendChart(QWidget):
    """Custom-painted chart of XP gains (line) and loot collected (bars) over time.

    Works both for a historical series (``set_data``) and for a live runtime feed
    (``append_sample``). Colours follow the active light/dark application theme.
    """

    #: Maximum number of samples retained for the live buffer.
    #: At the Runtime page's one-sample-per-second throttle this is ~10 minutes.
    MAX_POINTS = 600

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(220)
        self.xp_data = [0]
        self.loot_data = [0]
        self.hover_x = -1
        # Tracks whether the series still holds the initial placeholder point.
        # Comparing the data itself would misfire for a session that legitimately
        # starts at zero, silently discarding the opening samples.
        self._awaiting_first_sample = True
        self.setMouseTracking(True)  # Enable hover mouse movement tracking

    def set_data(self, xp_history: list[int], loot_history: list[int]) -> None:
        """Replace the full series (used by the historical Statistics view)."""
        self.xp_data = list(xp_history) if xp_history else [0]
        self.loot_data = list(loot_history) if loot_history else [0]
        self._awaiting_first_sample = False
        self.update()  # Request Qt canvas repaint event

    def append_sample(self, xp: int, loot: int) -> None:
        """Append one live telemetry point, trimming to ``MAX_POINTS``."""
        # A fresh live session starts from the placeholder [0]; drop it once real
        # data arrives so the trend does not begin with a spurious flat segment.
        if self._awaiting_first_sample:
            self.xp_data = []
            self.loot_data = []
            self._awaiting_first_sample = False
        self.xp_data.append(int(xp))
        self.loot_data.append(int(loot))
        if len(self.xp_data) > self.MAX_POINTS:
            self.xp_data = self.xp_data[-self.MAX_POINTS :]
            self.loot_data = self.loot_data[-self.MAX_POINTS :]
        self.update()

    def reset_live(self) -> None:
        """Clear the buffer back to the empty placeholder state."""
        self.xp_data = [0]
        self.loot_data = [0]
        self.hover_x = -1
        self._awaiting_first_sample = True
        self.update()

    def mouseMoveEvent(self, event) -> None:
        self.hover_x = event.position().x()
        self.update()

    def leaveEvent(self, event) -> None:
        self.hover_x = -1
        self.update()

    @staticmethod
    def _format_value(value: float) -> str:
        """Compact axis/tooltip formatting: 1500 -> '1.5k', 2_000_000 -> '2.0M'."""
        return _format_compact(value)

    def _theme_palette(self) -> dict:
        """Return chart colours matching the active application theme."""
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        theme_value = app.property("midgard_theme") if app is not None else None
        is_dark = theme_value != "light"  # default to dark when unset

        if is_dark:
            return {
                "surface": QColor("#141c29"),
                "grid": QColor(255, 255, 255, 28),
                "axis": QColor("#3a4a63"),
                "text": QColor("#e8edf5"),
                "muted": QColor("#8f9bad"),
                "xp": QColor("#3fd08f"),
                "loot": QColor(88, 152, 219, 150),
                "guide": QColor("#e0863a"),
                "bubble": QColor(8, 12, 20, 225),
                "bubble_text": QColor("#f2f5fa"),
            }
        return {
            "surface": QColor("#ffffff"),
            "grid": QColor(0, 0, 0, 22),
            "axis": QColor("#c3ccd6"),
            "text": QColor("#17202e"),
            "muted": QColor("#687588"),
            "xp": QColor("#0f9d63"),
            "loot": QColor(52, 120, 190, 120),
            "guide": QColor("#d97828"),
            "bubble": QColor(23, 32, 46, 235),
            "bubble_text": QColor("#f2f5fa"),
        }

    def paintEvent(self, event) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QFont, QPainter, QPen

        pal = self._theme_palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        # Rounded card-style background.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(pal["surface"])
        painter.drawRoundedRect(0, 0, w - 1, h - 1, 10, 10)

        pad_l, pad_t, pad_r, pad_b = 54, 18, 16, 46
        chart_w = w - pad_l - pad_r
        chart_h = h - pad_t - pad_b
        if chart_w <= 10 or chart_h <= 10:
            return

        base_y = h - pad_b
        n = len(self.xp_data)
        max_xp = max(self.xp_data) if self.xp_data else 0
        max_loot = max(self.loot_data) if self.loot_data else 0
        is_empty = max_xp == 0 and max_loot == 0

        small_font = QFont("Segoe UI", 8)
        painter.setFont(small_font)

        # --- Horizontal grid lines with XP-scaled numeric labels ---
        scale_xp = max_xp if max_xp > 0 else 1
        for k in range(5):
            frac = k / 4
            gy = int(pad_t + chart_h * frac)
            painter.setPen(QPen(pal["grid"], 1, Qt.PenStyle.DashLine))
            painter.drawLine(pad_l, gy, w - pad_r, gy)
            label = self._format_value(scale_xp * (1 - frac))
            painter.setPen(pal["muted"])
            painter.drawText(4, gy + 4, pad_l - 8, 12, Qt.AlignmentFlag.AlignRight, label)

        # --- Axes ---
        painter.setPen(QPen(pal["axis"], 1))
        painter.drawLine(pad_l, pad_t, pad_l, base_y)
        painter.drawLine(pad_l, base_y, w - pad_r, base_y)

        def x_at(i: int) -> int:
            if n <= 1:
                return pad_l + chart_w // 2
            return pad_l + int(chart_w * i / (n - 1))

        if is_empty:
            painter.setPen(pal["muted"])
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(
                pad_l,
                pad_t,
                chart_w,
                chart_h,
                Qt.AlignmentFlag.AlignCenter,
                "Waiting for runtime telemetry…",
            )
            return

        # --- Loot bars (drawn behind the XP line) ---
        loot_scale = max_loot if max_loot > 0 else 1
        slot = chart_w / max(1, n)
        bar_w = max(2, int(slot * 0.55))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(pal["loot"])
        for i, val in enumerate(self.loot_data):
            if val <= 0:
                continue
            bar_h = int(chart_h * val / loot_scale)
            cx = x_at(i) - bar_w // 2
            painter.drawRect(cx, base_y - bar_h, bar_w, bar_h)

        # --- XP line ---
        xp_scale = max_xp if max_xp > 0 else 1
        points = [
            (x_at(i), base_y - int(chart_h * val / xp_scale)) for i, val in enumerate(self.xp_data)
        ]
        painter.setPen(QPen(pal["xp"], 2))
        if len(points) == 1:
            px, py = points[0]
            painter.setBrush(pal["xp"])
            painter.drawEllipse(px - 3, py - 3, 6, 6)
        else:
            for i in range(len(points) - 1):
                p1, p2 = points[i], points[i + 1]
                painter.drawLine(p1[0], p1[1], p2[0], p2[1])

        # --- Hover guide + tooltip ---
        if n >= 1 and pad_l <= self.hover_x <= w - pad_r:
            index = int(round((self.hover_x - pad_l) / chart_w * (n - 1))) if n > 1 else 0
            index = max(0, min(index, n - 1))
            curr_xp = self.xp_data[index]
            curr_loot = self.loot_data[index]
            target_x = x_at(index)

            painter.setPen(QPen(pal["guide"], 1))
            painter.drawLine(target_x, pad_t, target_x, base_y)

            bubble_w, bubble_h = 116, 44
            bx = min(max(target_x - bubble_w // 2, pad_l), w - pad_r - bubble_w)
            by = pad_t + 6
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(pal["bubble"])
            painter.drawRoundedRect(bx, by, bubble_w, bubble_h, 6, 6)
            painter.setPen(pal["bubble_text"])
            painter.setFont(small_font)
            painter.drawText(bx + 10, by + 18, f"XP: {self._format_value(curr_xp)}")
            painter.drawText(bx + 10, by + 34, f"Loot: {curr_loot} items")

        # --- Legend below the axis ---
        legend_y = h - pad_b + 22
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(pal["xp"])
        painter.drawRect(pad_l, legend_y - 8, 14, 4)
        painter.setPen(pal["muted"])
        painter.setFont(small_font)
        painter.drawText(pad_l + 20, legend_y, "XP gained")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(pal["loot"])
        painter.drawRect(pad_l + 100, legend_y - 10, 12, 10)
        painter.setPen(pal["muted"])
        painter.drawText(pad_l + 118, legend_y, "Loot collected")


class NavigationMapView(QWidget):
    """Renders the configured waypoint route as a numbered, connected path.

    Uses the same flat coordinate space the runtime uses for waypoints, so the
    preview matches how the engine walks the route. Colours follow the theme.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(420, 360)
        self.waypoints: list[tuple[int, int]] = []

    def set_waypoints(self, waypoints: list[tuple[int, int]]) -> None:
        self.waypoints = [(int(x), int(y)) for x, y in waypoints]
        self.update()

    def _theme_is_dark(self) -> bool:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        return (app.property("midgard_theme") if app is not None else None) != "light"

    def paintEvent(self, event) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor, QFont, QPainter, QPen

        is_dark = self._theme_is_dark()
        surface = QColor("#141c29") if is_dark else QColor("#ffffff")
        grid = QColor(255, 255, 255, 20) if is_dark else QColor(0, 0, 0, 18)
        muted = QColor("#8f9bad") if is_dark else QColor("#687588")
        line = QColor("#58d2b0") if is_dark else QColor("#0f9d63")
        start_c = QColor("#3fd08f")
        end_c = QColor("#f2635f")
        dot = QColor("#e0a33a")
        text_c = QColor("#e8edf5") if is_dark else QColor("#17202e")

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(surface)
        painter.drawRoundedRect(0, 0, w - 1, h - 1, 10, 10)

        pad = 28
        area_w, area_h = w - 2 * pad, h - 2 * pad
        if area_w <= 20 or area_h <= 20:
            return

        # Light reference grid.
        painter.setPen(QPen(grid, 1))
        for i in range(1, 4):
            gx = pad + area_w * i // 4
            gy = pad + area_h * i // 4
            painter.drawLine(gx, pad, gx, pad + area_h)
            painter.drawLine(pad, gy, pad + area_w, gy)

        if not self.waypoints:
            painter.setPen(muted)
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(
                pad,
                pad,
                area_w,
                area_h,
                Qt.AlignmentFlag.AlignCenter,
                "No waypoints configured.\nAdd them as x,y,wait;x,y,wait",
            )
            return

        xs = [p[0] for p in self.waypoints]
        ys = [p[1] for p in self.waypoints]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max(1, max_x - min_x)
        span_y = max(1, max_y - min_y)

        def to_screen(px: int, py: int) -> tuple[int, int]:
            # Uniform scale preserves the route's real proportions; y grows
            # downward to match the game's client coordinate space.
            scale = min(area_w / span_x, area_h / span_y)
            ox = pad + (area_w - span_x * scale) / 2
            oy = pad + (area_h - span_y * scale) / 2
            return int(ox + (px - min_x) * scale), int(oy + (py - min_y) * scale)

        points = [to_screen(px, py) for px, py in self.waypoints]

        # Connecting route line.
        painter.setPen(QPen(line, 2))
        for i in range(len(points) - 1):
            painter.drawLine(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1])

        # Waypoint markers, numbered in walk order.
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        for i, (sx, sy) in enumerate(points):
            if i == 0:
                colour = start_c
            elif i == len(points) - 1:
                colour = end_c
            else:
                colour = dot
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(colour)
            painter.drawEllipse(sx - 9, sy - 9, 18, 18)
            painter.setPen(QColor("#0c111b"))
            painter.drawText(
                sx - 9, sy - 9, 18, 18, Qt.AlignmentFlag.AlignCenter, str(i + 1)
            )

        # Caption with the coordinate range.
        painter.setPen(muted)
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(
            pad,
            h - pad + 6,
            area_w,
            18,
            Qt.AlignmentFlag.AlignLeft,
            f"{len(points)} waypoints · X {min_x}–{max_x} · Y {min_y}–{max_y}",
        )
        painter.setPen(text_c)


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

        # 2. Stats summary cards laid out as a responsive grid of metric tiles
        self.stats_layout = QVBoxLayout()
        self.stats_layout.setSpacing(12)

        self.xp_card = StatCard("XP Accumulated")
        self.loot_card = StatCard("Loot Collected")
        self.deaths_card = StatCard("Deaths")
        self.time_card = StatCard("Runtime")

        cards_grid = QGridLayout()
        cards_grid.setSpacing(10)
        cards_grid.addWidget(self.xp_card, 0, 0)
        cards_grid.addWidget(self.loot_card, 0, 1)
        cards_grid.addWidget(self.deaths_card, 1, 0)
        cards_grid.addWidget(self.time_card, 1, 1)
        self.stats_layout.addLayout(cards_grid)

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
            for card in (self.xp_card, self.loot_card, self.deaths_card, self.time_card):
                card.set_value("--")
            self.trend_chart.set_data([0], [0])
            return

        profile = self.profile_store.get_profile(profile_id)
        if profile and profile.stats:
            stats = profile.stats
            self.xp_card.set_value(f"{stats.experience_gained:,}")
            self.loot_card.set_value(f"{stats.loot_count:,}")
            self.deaths_card.set_value(f"{stats.deaths:,}", alert=stats.deaths > 0)
            self.time_card.set_value(_format_duration(stats.runtime_seconds))

            # Load the real recorded time series; fall back to a simple
            # start -> current cumulative pair when no samples exist yet.
            samples = self.profile_store.get_stat_samples(profile_id)
            if samples:
                xp_history = [s[0] for s in samples]
                loot_history = [s[1] for s in samples]
            elif stats.experience_gained > 0 or stats.loot_count > 0:
                xp_history = [0, stats.experience_gained]
                loot_history = [0, stats.loot_count]
            else:
                xp_history = [0]
                loot_history = [0]
            self.trend_chart.set_data(xp_history, loot_history)


class DashboardPage(Page):
    """Operational overview aggregating real data across every character profile."""

    # Automation modules and the (rule category, enabled key) that activates each.
    MODULES = [
        ("Healing", "healing", "heal.enabled"),
        ("Experience", "experience", "experience.enabled"),
        ("Looting", "looting", "loot.enabled"),
        ("Combat", "combat", "combat.enabled"),
        ("Navigation", "navigation", "navigation.enabled"),
        ("Consumables", "consumables", "consumables.enabled"),
        ("Stash", "stash", "stash.enabled"),
        ("Security", "security", "security.enabled"),
    ]

    def __init__(self, profile_store: ProfileStore) -> None:
        super().__init__(
            "Dashboard",
            "Operational overview of your Midgard Studio profiles.",
            "Aggregate Statistics",
            "Combined totals across every character profile stored locally.",
            card_eyebrow="OVERVIEW",
        )
        self.profile_store = profile_store

        # Aggregate metric tiles (all profiles combined).
        self.profiles_card = StatCard("Profiles")
        self.xp_card = StatCard("Total XP")
        self.loot_card = StatCard("Total Loot")
        self.deaths_card = StatCard("Total Deaths")
        self.runtime_card = StatCard("Total Runtime")

        grid = QGridLayout()
        grid.setSpacing(10)
        for col, card in enumerate(
            (self.profiles_card, self.xp_card, self.loot_card, self.deaths_card, self.runtime_card)
        ):
            grid.addWidget(card, 0, col)
        self.card_layout.addLayout(grid)

        # Per-profile module-configuration overview.
        overview_card = QFrame()
        overview_card.setObjectName("contentCard")
        overview_layout = QVBoxLayout(overview_card)
        overview_layout.setContentsMargins(20, 18, 20, 18)
        overview_layout.setSpacing(10)

        header = QLabel("Profiles & Configured Modules")
        header.setObjectName("cardTitle")
        overview_layout.addWidget(header)

        self.profiles_container = QVBoxLayout()
        self.profiles_container.setSpacing(10)
        overview_layout.addLayout(self.profiles_container)

        self._empty_label = QLabel(
            "No profiles yet. Create one on the Profiles page to get started."
        )
        self._empty_label.setObjectName("cardBody")
        self._empty_label.setWordWrap(True)
        overview_layout.addWidget(self._empty_label)

        # Insert the overview card just above the trailing stretch of the page.
        layout = self.layout()
        layout.insertWidget(layout.count() - 1, overview_card)

        self._refresh()

    def showEvent(self, event) -> None:
        """Refresh aggregate data whenever the dashboard is shown."""
        super().showEvent(event)
        self._refresh()

    def _clear_profiles_container(self) -> None:
        while self.profiles_container.count():
            item = self.profiles_container.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _build_profile_row(self, profile) -> QFrame:
        """One row: profile name/class plus a chip per configured module."""
        row = QFrame()
        row.setObjectName("statCard")
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(14, 10, 14, 10)
        row_layout.setSpacing(6)

        title = QLabel(f"{profile.name}  ·  {profile.character_class}")
        title.setObjectName("sectionTitle")
        row_layout.addWidget(title)

        modules_row = QHBoxLayout()
        modules_row.setSpacing(14)
        any_on = False
        for label, category, enabled_key in self.MODULES:
            enabled = profile.rules.get(category, {}).get(enabled_key, "false").lower() == "true"
            any_on = any_on or enabled
            chip = QLabel(f"{'●' if enabled else '○'} {label}")
            chip.setObjectName("moduleOn" if enabled else "moduleOff")
            modules_row.addWidget(chip)
        modules_row.addStretch(1)
        row_layout.addLayout(modules_row)

        if not any_on:
            hint = QLabel("No automation modules enabled for this profile.")
            hint.setObjectName("moduleOff")
            row_layout.addWidget(hint)

        return row

    def _refresh(self) -> None:
        """Recompute aggregates and rebuild the per-profile overview."""
        profiles = self.profile_store.list_profiles()

        total_xp = sum(p.stats.experience_gained for p in profiles)
        total_loot = sum(p.stats.loot_count for p in profiles)
        total_deaths = sum(p.stats.deaths for p in profiles)
        total_runtime = sum(p.stats.runtime_seconds for p in profiles)

        self.profiles_card.set_value(str(len(profiles)))
        self.xp_card.set_value(_format_compact(total_xp))
        self.loot_card.set_value(_format_compact(total_loot))
        self.deaths_card.set_value(str(total_deaths), alert=total_deaths > 0)
        self.runtime_card.set_value(_format_duration(total_runtime))

        self._clear_profiles_container()
        self._empty_label.setVisible(not profiles)
        for profile in profiles:
            self.profiles_container.addWidget(self._build_profile_row(profile))


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
        self._init_experience_tab()
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

    def _init_experience_tab(self) -> None:
        tab = QWidget()
        layout = QFormLayout(tab)

        self.exp_enabled = QCheckBox("Enable Experience Tracking (OCR)")

        self.exp_x = QSpinBox()
        self.exp_x.setRange(0, 10000)
        self.exp_y = QSpinBox()
        self.exp_y.setRange(0, 10000)
        self.exp_w = QSpinBox()
        self.exp_w.setRange(1, 10000)
        self.exp_w.setValue(120)
        self.exp_h = QSpinBox()
        self.exp_h.setRange(1, 10000)
        self.exp_h.setValue(16)

        self.exp_interval = QDoubleSpinBox()
        self.exp_interval.setRange(0.2, 60.0)
        self.exp_interval.setValue(2.0)
        self.exp_interval.setSingleStep(0.5)

        self.exp_max_delta = QSpinBox()
        self.exp_max_delta.setRange(0, 100_000_000)
        self.exp_max_delta.setValue(0)

        layout.addRow(self.exp_enabled)
        layout.addRow(
            QLabel(
                "Select the on-screen region showing the numeric EXP value.\n"
                "The tracker reads it periodically and accumulates the increases."
            )
        )

        region_layout = QHBoxLayout()
        region_layout.addWidget(QLabel("X:"))
        region_layout.addWidget(self.exp_x)
        region_layout.addWidget(QLabel("Y:"))
        region_layout.addWidget(self.exp_y)
        region_layout.addWidget(QLabel("W:"))
        region_layout.addWidget(self.exp_w)
        region_layout.addWidget(QLabel("H:"))
        region_layout.addWidget(self.exp_h)

        self.exp_pick_btn = QPushButton("Select EXP Region")
        self.exp_pick_btn.clicked.connect(self._pick_experience_region)
        region_layout.addWidget(self.exp_pick_btn)

        layout.addRow("EXP Region", region_layout)
        layout.addRow("Sample Interval (s)", self.exp_interval)
        layout.addRow("Max Gain per Sample (0 = no limit)", self.exp_max_delta)

        self.exp_verify_btn = QPushButton("Verify EXP Reading")
        self.exp_verify_btn.clicked.connect(self._verify_experience_region)
        layout.addRow(self.exp_verify_btn)

        self.tab_widget.addTab(tab, "Experience")

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

        # Path Recorder Controls Row (TASK-033)
        from PySide6.QtWidgets import QPushButton, QSpinBox, QDoubleSpinBox
        layout.addWidget(QLabel("<b>Hunt Profile Path Recorder & Manager</b>"))
        recorder_layout = QHBoxLayout()
        self.nav_record_x = QSpinBox()
        self.nav_record_x.setRange(0, 3000)
        self.nav_record_x.setValue(100)
        
        self.nav_record_y = QSpinBox()
        self.nav_record_y.setRange(0, 3000)
        self.nav_record_y.setValue(100)

        self.nav_record_wait = QDoubleSpinBox()
        self.nav_record_wait.setRange(0.0, 60.0)
        self.nav_record_wait.setValue(3.0)

        record_btn = QPushButton("Record Waypoint")
        record_btn.clicked.connect(self._record_waypoint)
        
        recorder_layout.addWidget(QLabel("X:"))
        recorder_layout.addWidget(self.nav_record_x)
        recorder_layout.addWidget(QLabel("Y:"))
        recorder_layout.addWidget(self.nav_record_y)
        recorder_layout.addWidget(QLabel("Wait (s):"))
        recorder_layout.addWidget(self.nav_record_wait)
        recorder_layout.addWidget(record_btn)
        layout.addLayout(recorder_layout)

        file_actions_layout = QHBoxLayout()
        self.nav_path_filename = QLineEdit()
        self.nav_path_filename.setPlaceholderText("e.g. paths/payon.json")
        self.nav_path_filename.setText("paths/hunt_route.json")
        
        save_path_btn = QPushButton("Save Path File")
        save_path_btn.clicked.connect(self._save_path_file)
        
        load_path_btn = QPushButton("Load Path File")
        load_path_btn.clicked.connect(self._load_path_file)
        
        file_actions_layout.addWidget(self.nav_path_filename)
        file_actions_layout.addWidget(save_path_btn)
        file_actions_layout.addWidget(load_path_btn)
        layout.addLayout(file_actions_layout)

        preview_btn = QPushButton("Preview Route Map")
        preview_btn.clicked.connect(self._preview_navigation_route)
        layout.addWidget(preview_btn)

        # Custom Script Loader Settings Row (TASK-034)
        layout.addWidget(QLabel("<b>Custom Script Hot-Plugin Loader (.py)</b>"))
        script_layout = QFormLayout()
        self.nav_custom_script = QLineEdit()
        self.nav_custom_script.setPlaceholderText("e.g. scripts/custom_anti_trap.py")
        script_layout.addRow("Python Script Path", self.nav_custom_script)
        layout.addLayout(script_layout)

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
        exp = rules.get("experience", {})
        self.exp_enabled.setChecked(exp.get("experience.enabled", "false").lower() == "true")
        self.exp_x.setValue(int(exp.get("experience.x", "0")))
        self.exp_y.setValue(int(exp.get("experience.y", "0")))
        self.exp_w.setValue(int(exp.get("experience.w", "120")))
        self.exp_h.setValue(int(exp.get("experience.h", "16")))
        self.exp_interval.setValue(float(exp.get("experience.interval", "2.0")))
        self.exp_max_delta.setValue(int(exp.get("experience.max_delta", "0")))

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
        
        # Load custom script plugin settings (TASK-034)
        self.nav_custom_script.setText(nav.get("navigation.custom_script", ""))

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
                profile_id,
                "experience",
                "experience.enabled",
                str(self.exp_enabled.isChecked()).lower(),
            )
            self.profile_store.set_rule(
                profile_id, "experience", "experience.x", str(self.exp_x.value())
            )
            self.profile_store.set_rule(
                profile_id, "experience", "experience.y", str(self.exp_y.value())
            )
            self.profile_store.set_rule(
                profile_id, "experience", "experience.w", str(self.exp_w.value())
            )
            self.profile_store.set_rule(
                profile_id, "experience", "experience.h", str(self.exp_h.value())
            )
            self.profile_store.set_rule(
                profile_id, "experience", "experience.interval", str(self.exp_interval.value())
            )
            self.profile_store.set_rule(
                profile_id, "experience", "experience.max_delta", str(self.exp_max_delta.value())
            )
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
            
            # Save custom script plugin settings (TASK-034)
            self.profile_store.set_rule(
                profile_id,
                "navigation",
                "navigation.custom_script",
                self.nav_custom_script.text().strip(),
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
            # Fallback final: Try connecting using the bare profile name as title (TASK-035)
            try:
                capture_service = WindowCaptureService.from_title(profile.name)
                pil_img = capture_service.capture()
                pil_img = pil_img.convert("RGBA")
                data = bytes(pil_img.tobytes("raw", "RGBA"))
                qimg = QImage(data, pil_img.width(), pil_img.height(), QImage.Format.Format_RGBA8888)
                return QPixmap.fromImage(qimg)
            except Exception:
                pass

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
        """Capture the HP text bounding box coordinates and size."""
        pixmap = self._capture_game_window()
        if pixmap is None:
            return
        dialog = PickDialog(pixmap, self)
        if dialog.exec() == QDialog.Accepted:
            if dialog.selected_x is not None:
                self.heal_hp_x.setValue(dialog.selected_x)
                self.heal_hp_y.setValue(dialog.selected_y)
                if dialog.selected_w is not None and dialog.selected_w > 0:
                    self.heal_hp_w.setValue(dialog.selected_w)
                    self.heal_hp_h.setValue(dialog.selected_h)

    def _pick_sp_crop(self) -> None:
        """Capture the SP text bounding box coordinates and size."""
        pixmap = self._capture_game_window()
        if pixmap is None:
            return
        dialog = PickDialog(pixmap, self)
        if dialog.exec() == QDialog.Accepted:
            if dialog.selected_x is not None:
                self.heal_sp_x.setValue(dialog.selected_x)
                self.heal_sp_y.setValue(dialog.selected_y)
                if dialog.selected_w is not None and dialog.selected_w > 0:
                    self.heal_sp_w.setValue(dialog.selected_w)
                    self.heal_sp_h.setValue(dialog.selected_h)

    @staticmethod
    def _pixmap_to_pil(pixmap) -> Image.Image:
        """Convert a captured QPixmap into a PIL image for the vision helpers."""
        qimg = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        img_bytes = qimg.constBits().tobytes()
        return Image.frombytes("RGBA", (qimg.width(), qimg.height()), img_bytes)

    def _preview_navigation_route(self) -> None:
        """Show the configured waypoints as a route map for visual verification."""
        from midgard.runtime.input import DummyInputAdapter
        from midgard.runtime.navigation import NavigationModule

        raw = self.nav_waypoints_text.toPlainText().strip()
        # Reuse the runtime parser so the preview matches how the engine reads the
        # route, including JSON path-file support.
        module = NavigationModule(
            {"navigation.enabled": "true", "navigation.waypoints": raw},
            DummyInputAdapter(),
            hwnd=0,
        )
        waypoints = [(wx, wy) for wx, wy, _wait in module.waypoints]

        if not waypoints:
            QMessageBox.information(
                self,
                "Route Preview",
                "No waypoints to preview. Add them as x,y,wait;x,y,wait "
                "or load a path file first.",
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Navigation Route Preview")
        dialog.setMinimumSize(560, 520)
        dlg_layout = QVBoxLayout(dialog)

        view = NavigationMapView()
        view.set_waypoints(waypoints)
        dlg_layout.addWidget(view, 1)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        dlg_layout.addWidget(close_btn)

        dialog.exec()

    def _pick_experience_region(self) -> None:
        """Capture the EXP counter bounding box coordinates and size."""
        pixmap = self._capture_game_window()
        if pixmap is None:
            return
        dialog = PickDialog(pixmap, self)
        if dialog.exec() == QDialog.Accepted:
            if dialog.selected_x is not None:
                self.exp_x.setValue(dialog.selected_x)
                self.exp_y.setValue(dialog.selected_y)
                if dialog.selected_w is not None and dialog.selected_w > 0:
                    self.exp_w.setValue(dialog.selected_w)
                    self.exp_h.setValue(dialog.selected_h)

    def _verify_experience_region(self) -> None:
        """Read the configured EXP region once and report what OCR resolved."""
        pixmap = self._capture_game_window()
        if pixmap is None:
            return
        try:
            from midgard.runtime.experience import ExperienceTracker

            image = self._pixmap_to_pil(pixmap)
            tracker = ExperienceTracker(
                {
                    "experience.enabled": "true",
                    "experience.x": str(self.exp_x.value()),
                    "experience.y": str(self.exp_y.value()),
                    "experience.w": str(self.exp_w.value()),
                    "experience.h": str(self.exp_h.value()),
                }
            )
            value = tracker.read_value(image)
        except Exception as exc:
            QMessageBox.critical(self, "Verify EXP", f"Failed to read region: {exc}")
            return

        if value is None:
            QMessageBox.warning(
                self,
                "Verify EXP",
                "No number could be read from the selected region.\n"
                "Adjust the region so it tightly frames the EXP digits.",
            )
        else:
            QMessageBox.information(self, "Verify EXP", f"OCR resolved the value: {value}")

    def _verify_healing_crops(self) -> None:
        """Capture the current frame, crop HP/SP bounding boxes, parse them with OCR, and show visual dialog."""
        pixmap = self._capture_game_window()
        if pixmap is None:
            return

        # Convert QPixmap to PIL image
        pil_img = self._pixmap_to_pil(pixmap)
        img_w, img_h = pil_img.size

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

        # Parse through HSV pixel counter
        from midgard.runtime.heal import calculate_bar_percentage
        
        hp_pct = calculate_bar_percentage(hp_crop)
        sp_pct = calculate_bar_percentage(sp_crop)

        # Construct visual modal dialog to display result
        dialog = QDialog(self)
        dialog.setWindowTitle("Verify Crop & Bar Fill Output")
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
        hp_label = QLabel("<b>HP Crop Area (Scaled x3):</b>")
        hp_img_lbl = QLabel()
        hp_img_lbl.setPixmap(pil_to_pixmap(hp_crop))
        hp_res_lbl = QLabel(f"Calculated HP Fill: <b>{hp_pct:.1f}%</b>")
        
        diag_layout.addWidget(hp_label)
        diag_layout.addWidget(hp_img_lbl)
        diag_layout.addWidget(hp_res_lbl)

        # SP visual block
        sp_label = QLabel("<br><b>SP Crop Area (Scaled x3):</b>")
        sp_img_lbl = QLabel()
        sp_img_lbl.setPixmap(pil_to_pixmap(sp_crop))
        sp_res_lbl = QLabel(f"Calculated SP Fill: <b>{sp_pct:.1f}%</b>")

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
            # Bind character profile using the profile name + PID format (TASK-002)
            profile_name = profile.name
            new_title = f"{profile_name} [PID: {dialog.selected_pid}]"
            
            # Physically rename the target window on OS level so from_title string matches (TASK-002)
            from midgard.vision.capture import rename_window
            rename_window(dialog.selected_hwnd, new_title)
            
            self.window_title_input.setText(new_title)
            # Persist directly in SQLite
            self.profile_store.update_profile_window_title(profile_id, new_title)
            QMessageBox.information(
                self,
                "Success",
                f"Successfully injected profile '{profile.name}'!\n"
                f"Bound & Renamed Window to: {new_title}",
            )

    def _record_waypoint(self) -> None:
        """Append current coordinate inputs to the main waypoints text area."""
        x = self.nav_record_x.value()
        y = self.nav_record_y.value()
        w = self.nav_record_wait.value()
        current_text = self.nav_waypoints_text.toPlainText().strip()
        new_segment = f"{x},{y},{w}"
        if current_text:
            self.nav_waypoints_text.setPlainText(f"{current_text};{new_segment}")
        else:
            self.nav_waypoints_text.setPlainText(new_segment)

    def _save_path_file(self) -> None:
        """Parse text area waypoints and serialize as JSON coordinates sequence to filename."""
        raw_str = self.nav_waypoints_text.toPlainText().strip()
        filename = self.nav_path_filename.text().strip()
        if not filename:
            QMessageBox.warning(self, "Invalid Path", "Please enter a valid path filename first.")
            return
            
        # Parse segments
        waypoints = []
        if raw_str:
            for seg in raw_str.split(";"):
                parts = seg.split(",")
                if len(parts) == 3:
                    try:
                        waypoints.append([int(parts[0]), int(parts[1]), float(parts[2])])
                    except ValueError:
                        pass
                        
        from pathlib import Path
        import json
        try:
            p = Path(filename)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w") as f:
                json.dump(waypoints, f, indent=2)
            QMessageBox.information(self, "Success", f"Successfully saved path file to '{filename}'.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save path file: {e}")

    def _load_path_file(self) -> None:
        """Deserialize JSON coordinates path file and load waypoints into text area."""
        filename = self.nav_path_filename.text().strip()
        from pathlib import Path
        import json
        p = Path(filename)
        if not p.exists():
            QMessageBox.warning(self, "Not Found", f"No path file found at: '{filename}'")
            return
            
        try:
            with open(p, "r") as f:
                data = json.load(f)
            segments = []
            for item in data:
                if len(item) == 3:
                    segments.append(f"{item[0]},{item[1]},{item[2]}")
            self.nav_waypoints_text.setPlainText(";".join(segments))
            QMessageBox.information(self, "Success", f"Successfully loaded path file '{filename}'.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load path file: {e}")
