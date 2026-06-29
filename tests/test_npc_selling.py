"""Tests for NPC merchant selling loop dialog progression in StashModule."""

import pytest
from unittest.mock import MagicMock
from PIL import Image

from midgard.runtime.stash import StashModule


def test_stash_npc_sell_loop_progression() -> None:
    """StashModule executes Kafra storage banking and subsequent NPC store selling clicks."""
    mock_input = MagicMock()
    
    rules = {
        "stash.enabled": "true",
        "stash.teleport_hotkey": "F10",
        "stash.kafra_x": "300",
        "stash.kafra_y": "300",
        "stash.weight_check_x": "10",
        "stash.weight_check_y": "10",
        "stash.weight_color_r": "255",
        "stash.weight_color_g": "120",
        "stash.weight_color_b": "0",
        "stash.color_tolerance": "10",
        "stash.restock_enabled": "false",
        "stash.sell_enabled": "true",
        "stash.sell_npc_x": "520",
        "stash.sell_npc_y": "540",
    }
    
    stash = StashModule(rules, mock_input)
    assert not stash.is_banking

    # 1. Simulate weight check matches warning (orange pixel 255, 120, 0)
    img = Image.new("RGB", (20, 20), color=(255, 120, 0))
    log1 = stash.evaluate(img, hwnd=123)
    assert log1 is not None
    assert "Weight Overloaded" in log1
    assert stash.is_banking
    mock_input.tap_key.assert_called_with("F10")

    # 2. Progress banking cycle tick (clicks Kafra and sells at NPC merchant)
    log2 = stash.evaluate(img, hwnd=123)
    assert log2 is not None
    assert "Kafra banking cycle completed" in log2
    assert "Sold junk items at NPC store (520, 540)" in log2
    assert not stash.is_banking
    
    # Assert click sequences
    # Kafra NPC click
    mock_input.move_mouse_relative.assert_any_call(123, 300, 300)
    # Kafra Dialog selection click
    mock_input.move_mouse_relative.assert_any_call(123, 300, 340)
    
    # NPC Merchant click
    mock_input.move_mouse_relative.assert_any_call(123, 520, 540)
    # Sell Items Option click
    mock_input.move_mouse_relative.assert_any_call(123, 520, 580)
    # Confirm Sell click
    mock_input.move_mouse_relative.assert_any_call(123, 570, 620)
