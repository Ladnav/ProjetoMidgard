"""Tests for Auto-Stash inventory weight checks and Kafra dialog banking loops."""

import pytest
from unittest.mock import MagicMock
from PIL import Image

from midgard.runtime.stash import StashModule


def test_stash_module_weight_trigger_and_banking_dialogs() -> None:
    """StashModule detects orange/red weight warnings and steps through Kafra banking actions."""
    mock_input = MagicMock()
    
    rules = {
        "stash.enabled": "true",
        "stash.teleport_hotkey": "F9",
        "stash.kafra_x": "320",
        "stash.kafra_y": "280",
        "stash.weight_check_x": "5",
        "stash.weight_check_y": "5",
        "stash.weight_color_r": "250",
        "stash.weight_color_g": "120",
        "stash.weight_color_b": "10",
        "stash.color_tolerance": "15",
    }

    stash = StashModule(rules, mock_input)

    # 1. Image has regular color -> no trigger
    regular_img = Image.new("RGB", (20, 20), color=(0, 0, 0))
    res = stash.evaluate(regular_img, hwnd=123)
    assert res is None
    assert stash.is_banking is False

    # 2. Reset cooldown check and evaluate matching weight alert pixel -> initiates teleport
    stash.last_check_time = 0.0
    alert_img = Image.new("RGB", (20, 20), color=(0, 0, 0))
    alert_img.putpixel((5, 5), (251, 122, 9)) # Matches 250, 120, 10 closely
    res = stash.evaluate(alert_img, hwnd=123)
    
    assert res is not None
    assert "Weight Overloaded" in res
    assert stash.is_banking is True
    mock_input.tap_key.assert_called_with("F9")

    # 3. Next tick executes storage clicks since is_banking is True
    res_bank = stash.evaluate(alert_img, hwnd=123)
    assert res_bank is not None
    assert "Kafra banking cycle completed" in res_bank
    assert stash.is_banking is False
    assert mock_input.click_mouse.call_count > 0
