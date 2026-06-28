"""Tests for the Auto-Loot Module."""

import pytest
from unittest.mock import MagicMock
from PIL import Image

from midgard.runtime.loot import LootModule


def test_looting_module_finds_color_centroid_and_clicks() -> None:
    """LootModule scans image, calculates centroid of matching grey nameplate pixels, and clicks."""
    # Create mock input adapter
    mock_input = MagicMock()

    # Define simple rules
    rules = {
        "loot.enabled": "true",
        "loot.color.r": "220",
        "loot.color.g": "220",
        "loot.color.b": "220",
        "loot.color.tolerance": "10",
        "loot.cooldown": "0.0",  # Disable delay for instant test evaluation
        "loot.step_x": "2",
        "loot.step_y": "2",
    }

    loot = LootModule(rules, mock_input)

    # 1. Test image with no matching loot colors (all black)
    black_img = Image.new("RGB", (20, 20), color=(0, 0, 0))
    res = loot.evaluate(black_img)
    assert res is None
    assert mock_input.move_mouse.call_count == 0

    # 2. Test image with loot color cluster at (10, 10)
    loot_img = Image.new("RGB", (20, 20), color=(0, 0, 0))
    # Draw a 4x4 nameplate block centered at (10, 10)
    for x in range(8, 12):
        for y in range(8, 12):
            loot_img.putpixel((x, y), (220, 220, 220))

    res = loot.evaluate(loot_img)
    assert res is not None
    assert "Auto-Loot clicked on item label" in res

    # Verify mouse coordinates centroid computation
    # Centroid of square from 8 to 11 is (8+9+10+11)/4 = 9.5 -> integer floor 9
    mock_input.move_mouse.assert_called_with(9, 9)
    assert mock_input.click_mouse.call_count == 1
