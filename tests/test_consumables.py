"""Tests for Midgard Consumables & Buffs Module."""

from unittest.mock import MagicMock

from PIL import Image

from midgard.runtime.consumables import ConsumablesModule
from midgard.runtime.engine import RuntimeEngine
from midgard.runtime.input import SCAN_CODES, DummyInputAdapter


def test_consumables_parsing() -> None:
    """ConsumablesModule parses item strings correctly."""
    adapter = DummyInputAdapter()
    rules = {
        "consumables.enabled": "true",
        "consumables.items": (
            "concentration,F5,1800.0; agi_up, F6, 240.0; invalid; blessing, F7, 120.0"
        ),
    }
    module = ConsumablesModule(rules, adapter)

    assert len(module.items) == 3
    assert module.items[0] == ("concentration", "F5", 1800.0)
    assert module.items[1] == ("agi_up", "F6", 240.0)
    assert module.items[2] == ("blessing", "F7", 120.0)


def test_consumables_triggers_on_expiration() -> None:
    """ConsumablesModule triggers the hotkey when buff expires."""
    adapter = DummyInputAdapter()
    rules = {
        "consumables.enabled": "true",
        "consumables.items": "concentration,F1,5.0",
    }
    module = ConsumablesModule(rules, adapter)
    img = Image.new("RGB", (10, 10))

    # First eval should cast instantly (never cast before)
    res1 = module.evaluate(img)
    assert res1 is not None
    assert "concentration" in res1
    assert adapter.history == [("press", SCAN_CODES["F1"]), ("release", SCAN_CODES["F1"])]

    # Immediate second eval should skip (not expired)
    res2 = module.evaluate(img)
    assert res2 is None


def test_priority_hierarchy_with_consumables() -> None:
    """Engine tick priority logic interrupts combat and navigation when a consumable recasts."""
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

    # Mock modules
    engine.heal_module = MagicMock()
    engine.consumables_module = MagicMock()
    engine.combat_module = MagicMock()
    engine.navigation_module = MagicMock()

    # Scenario: Heal does NOT trigger, Consumables triggers -> Combat/Nav should not evaluate
    engine.heal_module.evaluate.return_value = None
    engine.consumables_module.evaluate.return_value = "Recast Buff"
    engine.combat_module.evaluate.return_value = "Combat Triggered"
    engine.navigation_module.evaluate.return_value = "Nav Triggered"

    engine._sock = MagicMock()
    engine._tick()

    engine.heal_module.evaluate.assert_called_once_with(mock_image)
    engine.consumables_module.evaluate.assert_called_once_with(mock_image)
    engine.combat_module.evaluate.assert_not_called()
    engine.navigation_module.evaluate.assert_not_called()
