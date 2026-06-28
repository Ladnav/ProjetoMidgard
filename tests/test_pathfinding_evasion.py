"""Tests for A* Pathfinding and Emergency Evasion Modules."""

from midgard.runtime.evasion import EvasionModule
from midgard.runtime.input import SCAN_CODES, DummyInputAdapter
from midgard.runtime.pathfinding import AStarNavigator


def test_astar_pathfinding_basic() -> None:
    """AStarNavigator finds a simple path around an obstacle."""
    # 0 = walkable, 1 = obstacle
    grid = [
        [0, 0, 0],
        [0, 1, 0],
        [0, 0, 0],
    ]
    navigator = AStarNavigator(grid)

    # Path around grid[1][1] (blocked)
    start = (0, 0)
    end = (2, 2)
    path = navigator.find_path(start, end)

    assert path is not None
    assert start in path
    assert end in path
    # Path must avoid (1, 1)
    assert (1, 1) not in path
    # Path coordinates must be walkable
    for x, y in path:
        assert grid[y][x] == 0


def test_astar_no_path() -> None:
    """AStarNavigator returns None if target is blocked or unreachable."""
    grid = [
        [0, 1, 0],
        [1, 1, 0],
        [0, 0, 0],
    ]
    navigator = AStarNavigator(grid)
    assert navigator.find_path((0, 0), (2, 0)) is None
    # Blocked end node
    assert navigator.find_path((0, 0), (1, 1)) is None


def test_evasion_module_panic_trigger() -> None:
    """EvasionModule triggers evasion hotkey when health drops below panic threshold."""
    rules = {
        "evasion.enabled": "true",
        "evasion.panic_hp_threshold": "25.0",
        "evasion.key": "F9",
        "evasion.min_cooldown": "0.0",
        "evasion.max_cooldown": "0.0",
    }
    input_adapter = DummyInputAdapter()
    module = EvasionModule(rules, input_adapter)

    # Safe health level
    log1 = module.evaluate_hp(30.0)
    assert log1 is None
    assert ("press", SCAN_CODES["F9"]) not in input_adapter.history

    # Danger health level
    log2 = module.evaluate_hp(20.0)
    assert log2 is not None
    assert "CRITICAL" in log2
    assert ("press", SCAN_CODES["F9"]) in input_adapter.history


def test_evasion_module_disabled() -> None:
    """EvasionModule does not trigger if disabled."""
    rules = {
        "evasion.enabled": "false",
        "evasion.panic_hp_threshold": "25.0",
        "evasion.key": "F9",
    }
    input_adapter = DummyInputAdapter()
    module = EvasionModule(rules, input_adapter)

    assert module.evaluate_hp(10.0) is None
    assert ("press", SCAN_CODES["F9"]) not in input_adapter.history
