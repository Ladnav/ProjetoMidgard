"""Tests for visual PNG/BMP and JSON grid mesh navigation pathfinding."""

import json
from unittest.mock import MagicMock

from PIL import Image

from midgard.runtime.navigation import NavigationModule, _to_astar_grid


def test_to_astar_grid_inverts_walkable_convention() -> None:
    """Navigation maps use 1 = walkable; the pathfinder uses 0 = walkable."""
    nav_grid = [[1, 0, 1], [1, 1, 0]]
    assert _to_astar_grid(nav_grid) == [[0, 1, 0], [0, 0, 1]]


def test_navigation_loads_visual_png_obstacles(tmp_path) -> None:
    """A PNG obstacle map drives real A* routing between waypoints, not a direct click."""
    mock_input = MagicMock()

    # 3x2 map, all walkable (white) except a wall at (1, 0).
    map_file = tmp_path / "map_mesh.png"
    img = Image.new("RGB", (3, 2), color=(255, 255, 255))
    img.putpixel((1, 0), (0, 0, 0))  # wall at center-top
    img.save(map_file)

    rules = {
        "navigation.enabled": "true",
        # Two waypoints so the engine routes from one to the other.
        "navigation.waypoints": "0,0,1.0;2,0,1.0",
        "navigation.map_file": str(map_file),
    }

    nav = NavigationModule(rules, mock_input, hwnd=123)
    res = nav.evaluate(Image.new("RGB", (20, 20), color=(0, 0, 0)))

    assert res is not None
    # The A* branch runs (previously the inverted grid made find_path return None
    # and the engine silently fell back to a single direct click).
    assert "A* path traversal" in res
    assert mock_input.click_mouse.call_count > 1  # multiple routed steps


def test_navigation_loads_json_matrix_obstacles(tmp_path) -> None:
    """A JSON walkable matrix (1 = walkable) drives real A* routing."""
    mock_input = MagicMock()

    grid_matrix = [
        [1, 0, 1],
        [1, 1, 1],
    ]
    map_file = tmp_path / "map_mesh.json"
    with open(map_file, "w") as f:
        json.dump(grid_matrix, f)

    rules = {
        "navigation.enabled": "true",
        "navigation.waypoints": "0,0,1.0;2,0,1.0",
        "navigation.map_file": str(map_file),
    }

    nav = NavigationModule(rules, mock_input, hwnd=123)
    res = nav.evaluate(Image.new("RGB", (20, 20), color=(0, 0, 0)))

    assert res is not None
    assert "A* path traversal" in res
    assert mock_input.click_mouse.call_count > 1


def test_navigation_routes_from_previous_waypoint_not_origin(tmp_path) -> None:
    """A* starts at the previous waypoint, so a blocked map origin is irrelevant.

    Regression: the route used to start from a hardcoded (0, 0). Here (0, 0) is a
    wall, so a (0, 0)-based route would fail; routing from the previous waypoint
    still succeeds.
    """
    mock_input = MagicMock()

    grid_matrix = [
        [0, 1, 1],  # (0,0) is a wall in navigation convention
        [1, 1, 1],
    ]
    map_file = tmp_path / "blocked_origin.json"
    with open(map_file, "w") as f:
        json.dump(grid_matrix, f)

    rules = {
        "navigation.enabled": "true",
        # Previous waypoint (2,1) -> current (0,1); both walkable, origin unused.
        "navigation.waypoints": "0,1,1.0;2,1,1.0",
        "navigation.map_file": str(map_file),
    }

    nav = NavigationModule(rules, mock_input, hwnd=123)
    res = nav.evaluate(Image.new("RGB", (20, 20), color=(0, 0, 0)))

    assert res is not None
    assert "A* path traversal" in res
