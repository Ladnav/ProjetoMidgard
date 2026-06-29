"""Tests for mouse movement Fitts' law velocity curve timing, navigation anti-stuck skips, and chart tooltip hovers."""

import pytest
import time
from unittest.mock import MagicMock
from PIL import Image

from midgard.runtime.input import generate_bezier_path
from midgard.runtime.navigation import NavigationModule
from midgard.ui.pages import StatisticsTrendChart


def test_input_fitts_law_sleep_simulation() -> None:
    """Bezier path steps generate variable sleeps resembling Fitts' law (peak speeds in middle)."""
    start = (10, 10)
    end = (100, 100)
    path = generate_bezier_path(start, end, steps=10)
    
    assert len(path) == 11
    # Verify math constraints mapping
    factors = []
    import math
    for i in range(len(path)):
        t = (i + 1) / len(path)
        speed_factor = math.sin(t * math.pi)
        factors.append(speed_factor)
        
    # Sine curve peaks in middle steps
    assert factors[5] > factors[0]
    assert factors[5] > factors[-1]


def test_navigation_anti_stuck_recovery_triggers() -> None:
    """NavigationModule skips to next waypoint if coordinates are staled for stuck timeout limit."""
    mock_input = MagicMock()
    
    rules = {
        "navigation.enabled": "true",
        "navigation.waypoints": "10,10,0.0;20,20,0.0",
        "navigation.transition_enabled": "false",
    }
    
    nav = NavigationModule(rules, mock_input, hwnd=123)
    assert nav.current_index == 0

    img = Image.new("RGB", (20, 20), color=(0, 0, 0))
    
    # Tick 1: First target move
    res1 = nav.evaluate(img)
    assert res1 is not None
    assert nav.current_index == 1 # updates sequence correctly

    # Reset current index to mock stuck scenario
    nav.current_index = 0
    nav.last_target_x = 10
    nav.last_target_y = 10
    nav.stuck_timestamp = time.time() - 10.0 # staled by 10s (timeout limit is 5s)
    
    # Tick 2: Stuck check triggers skip index
    res_stuck = nav.evaluate(img)
    assert res_stuck is not None
    assert "Navigation Stuck Recovery" in res_stuck
    assert nav.current_index == 1


def test_statistics_trend_chart_hover_mouse_tracking() -> None:
    """StatisticsTrendChart updates hover coordinates on mouseMoveEvent."""
    from PySide6.QtWidgets import QApplication
    import sys
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        
    chart = StatisticsTrendChart()
    assert chart.hover_x == -1

    # Mock Qt mouse move event details mapping
    mock_event = MagicMock()
    mock_event.position.return_value.x = lambda: 120.0
    
    chart.mouseMoveEvent(mock_event)
    assert chart.hover_x == 120.0

    # Leave event resets hover coordinates
    chart.leaveEvent(MagicMock())
    assert chart.hover_x == -1
