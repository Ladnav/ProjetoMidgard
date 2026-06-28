"""Tests for Midgard Automation MVP components (Heal module and Input adapters)."""

from PIL import Image

from midgard.runtime.heal import HealModule
from midgard.runtime.input import SCAN_CODES, DummyInputAdapter


def test_dummy_input_adapter() -> None:
    """DummyInputAdapter records press and release events in memory."""
    adapter = DummyInputAdapter()
    adapter.press_key(SCAN_CODES["F1"])
    assert adapter.pressed_keys == [SCAN_CODES["F1"]]

    adapter.release_key(SCAN_CODES["F1"])
    assert adapter.pressed_keys == []
    assert adapter.history == [
        ("press", SCAN_CODES["F1"]),
        ("release", SCAN_CODES["F1"]),
    ]


def test_heal_module_does_not_trigger_when_disabled() -> None:
    """HealModule does not evaluate if disabled in rules configuration."""
    adapter = DummyInputAdapter()
    rules = {
        "heal.enabled": "false",
        "heal.hp_x": "10",
        "heal.hp_y": "10",
        "heal.hp_key": "F1",
    }
    module = HealModule(rules, adapter)

    # Empty 20x20 image
    img = Image.new("RGB", (20, 20), color=(0, 0, 0))
    result = module.evaluate(img)

    assert result is None
    assert len(adapter.history) == 0


def test_heal_module_trigger_on_low_health() -> None:
    """HealModule triggers hotkey if target coordinate color deviates from expected value."""
    adapter = DummyInputAdapter()
    rules = {
        "heal.enabled": "true",
        "heal.hp_x": "0",
        "heal.hp_y": "0",
        "heal.hp_w": "60",
        "heal.hp_h": "12",
        "heal.hp_threshold": "95.0",
        "heal.hp_key": "F3",
        "heal.min_cooldown": "0.0",
        "heal.max_cooldown": "0.0",
    }
    module = HealModule(rules, adapter)

    # 1. Healthy state (100% template matches 100% threshold)
    img_healthy = Image.new("RGB", (10, 10), color=(255, 255, 255))
    result_healthy = module.evaluate(img_healthy)
    assert result_healthy is None
    assert len(adapter.history) == 0

    # 2. Damaged/Low HP state (Black/empty returns 90% via OCR, triggering under 95% threshold)
    img_damaged = Image.new("RGB", (24, 10), color=(255, 255, 255))
    result_damaged = module.evaluate(img_damaged)
    assert result_damaged is not None
    assert "Tapped F3" in result_damaged

    # Tap key should have run press & release scan code events
    assert len(adapter.history) == 2
    assert adapter.history[0] == ("press", SCAN_CODES["F3"])
    assert adapter.history[1] == ("release", SCAN_CODES["F3"])


def test_heal_module_respects_cooldown() -> None:
    """HealModule bypasses execution if evaluate() is called within cooldown window."""
    adapter = DummyInputAdapter()
    rules = {
        "heal.enabled": "true",
        "heal.hp_x": "0",
        "heal.hp_y": "0",
        "heal.hp_w": "24",
        "heal.hp_h": "10",
        "heal.hp_threshold": "95.0",
        "heal.hp_key": "F1",
        "heal.min_cooldown": "5.0",  # Long cooldown
        "heal.max_cooldown": "5.0",
    }
    module = HealModule(rules, adapter)
    img_damaged = Image.new("RGB", (24, 10), color=(255, 255, 255))

    # First evaluation succeeds
    res1 = module.evaluate(img_damaged)
    assert res1 is not None

    # Second evaluation immediately after fails due to cooldown window
    res2 = module.evaluate(img_damaged)
    assert res2 is None
