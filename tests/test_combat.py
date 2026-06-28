"""Tests for Midgard Combat Module and Mouse Input Simulation."""

from PIL import Image

from midgard.runtime.combat import CombatModule
from midgard.runtime.input import DummyInputAdapter


def test_dummy_input_adapter_mouse_tracking() -> None:
    """DummyInputAdapter records mouse movement and click actions in memory."""
    adapter = DummyInputAdapter()
    adapter.move_mouse_relative(123456, 100, 200)
    assert adapter.mouse_x == 100
    assert adapter.mouse_y == 200

    adapter.click_mouse("left")
    adapter.click_mouse("right")

    assert adapter.history == [
        ("move_mouse", (100, 200)),
        ("click_mouse", "left"),
        ("click_mouse", "right"),
    ]


def test_combat_module_finds_centroid_target() -> None:
    """CombatModule scans the image and returns the centroid of target colors."""
    adapter = DummyInputAdapter()
    rules = {
        "combat.enabled": "true",
        "combat.target_r": "255",
        "combat.target_g": "0",
        "combat.target_b": "0",  # Red target
        "combat.color_tolerance": "10",
        "combat.step_x": "2",
        "combat.step_y": "2",
        "combat.min_hits": "3",
        "combat.min_cooldown": "0.0",
        "combat.max_cooldown": "0.0",
    }
    module = CombatModule(rules, adapter, hwnd=123)

    # 1. Image with no red pixels (Blue background)
    img_no_target = Image.new("RGB", (10, 10), color=(0, 0, 255))
    target = module.find_target(img_no_target)
    assert target is None

    # 2. Image with red pixels at specific positions:
    # We place red pixels at (2, 2), (2, 4), and (4, 2)
    # The average coordinate should be (2.66, 2.66) -> int -> (2, 2) or close
    img_with_target = Image.new("RGB", (10, 10), color=(0, 0, 255))
    pixels = img_with_target.load()
    pixels[2, 2] = (255, 0, 0)
    pixels[2, 4] = (255, 0, 0)
    pixels[4, 2] = (255, 0, 0)

    target_coords = module.find_target(img_with_target)
    assert target_coords is not None
    tx, ty = target_coords
    # Averaging: (2+2+4)/3 = 2.66 -> 2 (since int division in python centroid is 2.66 -> 2)
    # (2+4+2)/3 = 2.66 -> 2
    assert tx == 2
    assert ty == 2


def test_combat_module_evaluation_clicks_target() -> None:
    """CombatModule evaluation clicks on target coordinate if found."""
    adapter = DummyInputAdapter()
    rules = {
        "combat.enabled": "true",
        "combat.target_r": "255",
        "combat.target_g": "0",
        "combat.target_b": "0",
        "combat.color_tolerance": "10",
        "combat.step_x": "1",
        "combat.step_y": "1",
        "combat.min_hits": "1",
        "combat.min_cooldown": "0.0",
        "combat.max_cooldown": "0.0",
    }
    module = CombatModule(rules, adapter, hwnd=123456)

    # Image with target at (5, 5)
    img = Image.new("RGB", (10, 10), color=(0, 0, 255))
    img.putpixel((5, 5), (255, 0, 0))

    log_msg = module.evaluate(img)
    assert log_msg is not None
    assert "Found combat target at (5, 5)" in log_msg

    # Verify mouse actions recorded in DummyInputAdapter
    assert len(adapter.history) == 2
    assert adapter.history[0] == ("move_mouse", (5, 5))
    assert adapter.history[1] == ("click_mouse", "left")


def test_combat_module_cooldown() -> None:
    """CombatModule respects combat tick cooldown windows."""
    adapter = DummyInputAdapter()
    rules = {
        "combat.enabled": "true",
        "combat.target_r": "255",
        "combat.target_g": "0",
        "combat.target_b": "0",
        "combat.color_tolerance": "10",
        "combat.step_x": "1",
        "combat.step_y": "1",
        "combat.min_hits": "1",
        "combat.min_cooldown": "5.0",  # Long cooldown
        "combat.max_cooldown": "5.0",
    }
    module = CombatModule(rules, adapter, hwnd=123)

    img = Image.new("RGB", (5, 5), color=(255, 0, 0))

    # First evaluation succeeds
    res1 = module.evaluate(img)
    assert res1 is not None

    # Second evaluation immediately after fails due to cooldown
    res2 = module.evaluate(img)
    assert res2 is None
