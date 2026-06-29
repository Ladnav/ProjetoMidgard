"""Tests for hunt profile JSON path loading, saving, and GUI recording actions."""

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock
from PIL import Image

from midgard.runtime.navigation import NavigationModule


def test_navigation_dynamic_json_path_loading(tmp_path) -> None:
    """NavigationModule loads waypoint coordinate lists from serialized JSON path files."""
    path_file = tmp_path / "payon_walk.json"
    waypoints_data = [
        [120, 140, 2.5],
        [200, 220, 5.0]
    ]
    
    with open(path_file, "w") as f:
        json.dump(waypoints_data, f)

    mock_input = MagicMock()
    rules = {
        "navigation.enabled": "true",
        "navigation.waypoints": str(path_file),
        "navigation.transition_enabled": "false",
    }

    nav = NavigationModule(rules, mock_input, hwnd=123)
    assert len(nav.waypoints) == 2
    assert nav.waypoints[0] == (120, 140, 2.5)
    assert nav.waypoints[1] == (200, 220, 5.0)

    # Walk tick executes successfully
    img = Image.new("RGB", (20, 20), color=(0, 0, 0))
    log = nav.evaluate(img)
    assert log is not None
    assert "Navigation click at coordinate (120, 140)" in log
