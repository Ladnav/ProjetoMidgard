"""Tests for Midgard Waypoint Navigation and Priority Execution."""

from unittest.mock import MagicMock

from PIL import Image

from midgard.runtime.engine import RuntimeEngine
from midgard.runtime.input import DummyInputAdapter
from midgard.runtime.navigation import NavigationModule


def test_navigation_waypoint_parsing() -> None:
    """NavigationModule correctly parses coordinate strings into waypoint objects."""
    adapter = DummyInputAdapter()
    rules = {
        "navigation.enabled": "true",
        "navigation.waypoints": "100,200,1.5 ; 300,400,2.0 ; invalid,coords ; 500,600,0.5",
    }
    module = NavigationModule(rules, adapter, hwnd=123)

    assert len(module.waypoints) == 3
    assert module.waypoints[0] == (100, 200, 1.5)
    assert module.waypoints[1] == (300, 400, 2.0)
    assert module.waypoints[2] == (500, 600, 0.5)


def test_navigation_steps_sequentially() -> None:
    """NavigationModule moves sequentially through waypoints and loops back."""
    adapter = DummyInputAdapter()
    rules = {
        "navigation.enabled": "true",
        "navigation.waypoints": "10,10,0.0;20,20,0.0",
    }
    module = NavigationModule(rules, adapter, hwnd=123)
    img = Image.new("RGB", (30, 30))

    # Click index 0
    res1 = module.evaluate(img)
    assert "index 0" in res1
    assert adapter.history[-2] == ("move_mouse", (10, 10))
    assert adapter.history[-1] == ("click_mouse", "left")

    # Click index 1
    res2 = module.evaluate(img)
    assert "index 1" in res2
    assert adapter.history[-2] == ("move_mouse", (20, 20))
    assert adapter.history[-1] == ("click_mouse", "left")

    # Click index 0 again (loops back)
    res3 = module.evaluate(img)
    assert "index 0" in res3


def test_navigation_respects_wait_cooldown() -> None:
    """NavigationModule does not click if waypoint wait time hasn't expired."""
    adapter = DummyInputAdapter()
    rules = {
        "navigation.enabled": "true",
        "navigation.waypoints": "10,10,5.0;20,20,0.0",
    }
    module = NavigationModule(rules, adapter, hwnd=123)
    img = Image.new("RGB", (30, 30))

    # Click index 0
    res1 = module.evaluate(img)
    assert res1 is not None

    # Immediate second check fails due to wait_time
    res2 = module.evaluate(img)
    assert res2 is None


def test_priority_hierarchy_in_engine_loop() -> None:
    """Engine tick priority logic interrupts navigation if heal or combat triggers."""
    engine = RuntimeEngine(
        profile_id=1,
        database_path=None,
        studio_port=0,
        use_dummy_input=True,
    )

    # Mock screen capture
    mock_image = Image.new("RGB", (10, 10))
    engine.capture_service = MagicMock()
    engine.capture_service.capture.return_value = mock_image

    # Mock evaluation modules
    engine.heal_module = MagicMock()
    engine.combat_module = MagicMock()
    engine.navigation_module = MagicMock()

    # Scenario 1: Healing triggers -> Combat and Navigation should NOT evaluate
    engine.heal_module.evaluate.return_value = "Heal Triggered"
    engine.combat_module.evaluate.return_value = "Combat Triggered"
    engine.navigation_module.evaluate.return_value = "Nav Triggered"

    engine._sock = MagicMock()  # Mock IPC socket connection
    engine._tick()

    engine.heal_module.evaluate.assert_called_once_with(mock_image)
    engine.combat_module.evaluate.assert_not_called()
    engine.navigation_module.evaluate.assert_not_called()

    # Reset mocks
    engine.heal_module.reset_mock()
    engine.combat_module.reset_mock()
    engine.navigation_module.reset_mock()

    # Scenario 2: Healing does NOT trigger, Combat triggers -> Navigation should NOT evaluate
    engine.heal_module.evaluate.return_value = None
    engine.combat_module.evaluate.return_value = "Combat Triggered"

    engine._tick()

    engine.heal_module.evaluate.assert_called_once_with(mock_image)
    engine.combat_module.evaluate.assert_called_once_with(mock_image)
    engine.navigation_module.evaluate.assert_not_called()
