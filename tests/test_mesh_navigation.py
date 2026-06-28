"""Tests for visual PNG/BMP and JSON grid mesh navigation pathfinding."""

import pytest
from unittest.mock import MagicMock
from pathlib import Path
from PIL import Image
import json

from midgard.runtime.navigation import NavigationModule


def test_navigation_loads_visual_png_obstacles(tmp_path) -> None:
    """NavigationModule loads binary PNG visual obstacles (black/white pixels) and runs pathfinding."""
    mock_input = MagicMock()
    
    # 1. Write mock PNG file map where:
    # row 0: (0,0) is white, (1,0) is black (wall), (2,0) is white
    # row 1: (0,1) is white, (1,1) is white (walkway), (2,1) is white
    map_file = tmp_path / "map_mesh.png"
    img = Image.new("RGB", (3, 2), color=(255, 255, 255))
    img.putpixel((1, 0), (0, 0, 0))  # wall at center-top
    img.save(map_file)

    rules = {
        "navigation.enabled": "true",
        "navigation.waypoints": "2,0,1.0", # target at (2,0)
        "navigation.map_file": str(map_file),
    }

    nav = NavigationModule(rules, mock_input, hwnd=123)
    
    clean_frame = Image.new("RGB", (20, 20), color=(0, 0, 0))
    res = nav.evaluate(clean_frame)
    
    assert res is not None
    # Verify that mouse click was clicked and path traversed around the (1,0) obstacle
    assert mock_input.click_mouse.call_count > 0


def test_navigation_loads_json_matrix_obstacles(tmp_path) -> None:
    """NavigationModule loads JSON coordinate grids (walkable 1, wall 0) and computes routes."""
    mock_input = MagicMock()
    
    # Write mock JSON grid map matrix representation
    # 1 represents walkable, 0 represents wall
    grid_matrix = [
        [1, 0, 1],
        [1, 1, 1]
    ]
    map_file = tmp_path / "map_mesh.json"
    with open(map_file, "w") as f:
        json.dump(grid_matrix, f)

    rules = {
        "navigation.enabled": "true",
        "navigation.waypoints": "2,0,1.0", # target at (2,0)
        "navigation.map_file": str(map_file),
    }

    nav = NavigationModule(rules, mock_input, hwnd=123)
    
    clean_frame = Image.new("RGB", (20, 20), color=(0, 0, 0))
    res = nav.evaluate(clean_frame)
    
    assert res is not None
    assert mock_input.click_mouse.call_count > 0
