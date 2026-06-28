"""Page widgets used by the main application shell."""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from midgard.ui.theme import Theme


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
