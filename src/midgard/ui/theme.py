"""Midgard Studio visual themes."""

from enum import StrEnum


class Theme(StrEnum):
    """Supported application themes."""

    LIGHT = "light"
    DARK = "dark"

    @classmethod
    def from_value(cls, value: str | None) -> "Theme":
        """Return a valid theme, defaulting safely to dark."""
        try:
            return cls(value)
        except ValueError:
            return cls.DARK


THEME_SETTING_KEY = "appearance.theme"


def stylesheet(theme: Theme) -> str:
    """Return the complete application stylesheet for ``theme``."""
    colors = _COLORS[theme]
    return f"""
        QWidget {{
            color: {colors["text"]};
            background-color: {colors["background"]};
            font-family: "Segoe UI", "Inter", sans-serif;
            font-size: 14px;
        }}
        QLabel {{
            background-color: transparent;
        }}
        QMainWindow {{
            background-color: {colors["background"]};
        }}
        QWidget#sidebar {{
            background-color: {colors["sidebar"]};
            border-right: 1px solid {colors["border"]};
        }}
        QLabel#brandMark {{
            color: {colors["accent"]};
            font-size: 26px;
            font-weight: 700;
            letter-spacing: 2px;
        }}
        QLabel#brandSubtitle {{
            color: {colors["muted"]};
            font-size: 11px;
            letter-spacing: 1px;
        }}
        QPushButton#navButton {{
            background: transparent;
            border: 0;
            border-radius: 8px;
            color: {colors["muted"]};
            padding: 11px 14px;
            text-align: left;
            font-weight: 500;
        }}
        QPushButton#navButton:hover {{
            background-color: {colors["hover"]};
            color: {colors["text"]};
        }}
        QPushButton#navButton:checked {{
            background-color: {colors["selection"]};
            color: {colors["accent"]};
            font-weight: 650;
        }}
        QLabel#pageTitle {{
            color: {colors["text"]};
            font-size: 30px;
            font-weight: 700;
        }}
        QLabel#pageDescription {{
            color: {colors["muted"]};
            font-size: 14px;
        }}
        QFrame#contentCard {{
            background-color: {colors["surface"]};
            border: 1px solid {colors["border"]};
            border-radius: 12px;
        }}
        QLabel#cardEyebrow {{
            color: {colors["accent"]};
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1px;
        }}
        QLabel#cardTitle {{
            color: {colors["text"]};
            font-size: 19px;
            font-weight: 650;
        }}
        QLabel#cardBody, QLabel#sidebarFooter {{
            color: {colors["muted"]};
        }}
        QComboBox {{
            background-color: {colors["input"]};
            border: 1px solid {colors["border"]};
            border-radius: 7px;
            color: {colors["text"]};
            min-width: 180px;
            padding: 8px 12px;
        }}
        QComboBox:hover, QComboBox:focus {{
            border-color: {colors["accent"]};
        }}
        QComboBox QAbstractItemView {{
            background-color: {colors["surface"]};
            border: 1px solid {colors["border"]};
            color: {colors["text"]};
            selection-background-color: {colors["selection"]};
            selection-color: {colors["text"]};
        }}
        QStatusBar {{
            background-color: {colors["surface"]};
            border-top: 1px solid {colors["border"]};
            color: {colors["muted"]};
        }}
        QToolTip {{
            background-color: {colors["surface"]};
            border: 1px solid {colors["border"]};
            color: {colors["text"]};
            padding: 5px;
        }}
    """


_COLORS = {
    Theme.DARK: {
        "background": "#0c111b",
        "surface": "#141c29",
        "sidebar": "#101722",
        "input": "#0f1622",
        "border": "#273449",
        "text": "#e8edf5",
        "muted": "#8f9bad",
        "accent": "#58d2b0",
        "hover": "#192436",
        "selection": "#183d3b",
    },
    Theme.LIGHT: {
        "background": "#f3f6f9",
        "surface": "#ffffff",
        "sidebar": "#ffffff",
        "input": "#f7f9fb",
        "border": "#dce3ea",
        "text": "#17202e",
        "muted": "#687588",
        "accent": "#087f6b",
        "hover": "#f0f4f6",
        "selection": "#dff3ed",
    },
}
