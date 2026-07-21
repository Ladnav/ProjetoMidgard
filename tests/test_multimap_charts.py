"""Tests for multi-map transition navigation and custom statistics charting UI painting."""

import pytest
from unittest.mock import MagicMock
from PIL import Image

from midgard.runtime.navigation import NavigationModule
from midgard.ui.pages import StatisticsTrendChart


def test_navigation_multi_map_transitions() -> None:
    """NavigationModule intercepts path coordinates to cross portals if target map differs."""
    mock_input = MagicMock()
    
    rules = {
        "navigation.enabled": "true",
        "navigation.waypoints": "100,100,2.0",
        "navigation.transition_enabled": "true",
        "navigation.current_map": "prt_fild08",
        "navigation.target_map": "prt_fild05",
        "navigation.transitions": "prt_fild08:prt_fild05:360:20:5.0",
    }

    nav = NavigationModule(rules, mock_input, hwnd=123)
    assert nav.current_map == "prt_fild08"

    img = Image.new("RGB", (20, 20), color=(0, 0, 0))
    
    # 1. First evaluate intercepts destination to route to portal coordinate
    log_msg = nav.evaluate(img)
    assert log_msg is not None
    assert "Multi-Map Transition" in log_msg
    assert nav.current_map == "prt_fild05"
    mock_input.move_mouse_relative.assert_called_with(123, 360, 20)
    mock_input.click_mouse.assert_called_with("left")


def test_statistics_trend_chart_data_assignment() -> None:
    """StatisticsTrendChart successfully registers and repaints data series trends."""
    # Ensure QGuiApplication is mocked/instantiated correctly when creating Qt widgets
    from PySide6.QtWidgets import QApplication
    import sys
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        
    chart = StatisticsTrendChart()
    assert chart.xp_data == [0]
    assert chart.loot_data == [0]

    chart.set_data([10, 40, 100], [1, 2, 5])
    assert chart.xp_data == [10, 40, 100]
    assert chart.loot_data == [1, 2, 5]


def test_statistics_trend_chart_live_append_and_reset() -> None:
    """append_sample builds a live series, dropping the initial placeholder point."""
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    chart = StatisticsTrendChart()
    assert chart.xp_data == [0] and chart.loot_data == [0]

    # First real sample replaces the [0] placeholder rather than appending to it.
    chart.append_sample(120, 2)
    assert chart.xp_data == [120]
    assert chart.loot_data == [2]

    chart.append_sample(300, 5)
    assert chart.xp_data == [120, 300]
    assert chart.loot_data == [2, 5]

    # Buffer is capped at MAX_POINTS.
    for i in range(chart.MAX_POINTS + 50):
        chart.append_sample(i, i)
    assert len(chart.xp_data) == chart.MAX_POINTS
    assert len(chart.loot_data) == chart.MAX_POINTS

    chart.reset_live()
    assert chart.xp_data == [0]
    assert chart.loot_data == [0]


def test_live_chart_keeps_leading_zero_samples() -> None:
    """A session that legitimately starts at zero must not discard its samples.

    Regression test: the placeholder was detected by comparing the data to [0],
    so every zero-valued sample re-triggered the reset and the opening flat
    period of a run was silently thrown away.
    """
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    chart = StatisticsTrendChart()
    chart.append_sample(0, 0)
    chart.append_sample(0, 0)
    chart.append_sample(0, 0)
    chart.append_sample(150, 3)

    assert chart.xp_data == [0, 0, 0, 150]
    assert chart.loot_data == [0, 0, 0, 3]


def test_statistics_trend_chart_value_formatting() -> None:
    """Compact numeric formatting for axis and tooltip labels."""
    assert StatisticsTrendChart._format_value(500) == "500"
    assert StatisticsTrendChart._format_value(1500) == "1.5k"
    assert StatisticsTrendChart._format_value(2_000_000) == "2.0M"
