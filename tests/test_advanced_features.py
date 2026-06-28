"""Tests for visual active status bar checks, combat priority template folders, and rarity color-filtered looting."""

import pytest
from unittest.mock import MagicMock, patch
from PIL import Image
from pathlib import Path

from midgard.runtime.consumables import ConsumablesModule
from midgard.runtime.combat import CombatModule
from midgard.runtime.loot import LootModule


def test_status_bar_active_icon_checks() -> None:
    """ConsumablesModule bypasses buff recasting if active status bar pixel color matches."""
    mock_input = MagicMock()
    
    rules = {
        "consumables.enabled": "true",
        "consumables.items": "agi_up,F6,10.0",
        "consumables.status_bar_enabled": "true",
        "consumables.status_check_x": "5",
        "consumables.status_check_y": "5",
        "consumables.status_color_r": "100",
        "consumables.status_color_g": "150",
        "consumables.status_color_b": "200",
        "consumables.status_tolerance": "10",
    }
    
    cons = ConsumablesModule(rules, mock_input)

    # Case 1: Status icon pixel color DOES NOT match (active color absent) -> casts buff
    absent_img = Image.new("RGB", (10, 10), color=(0, 0, 0))
    res = cons.evaluate(absent_img)
    assert res is not None
    assert "agi_up" in res
    assert mock_input.tap_key.call_count == 1

    # Case 2: Status icon pixel matches closely (active color present) -> skips casting
    mock_input.reset_mock()
    active_img = Image.new("RGB", (10, 10), color=(0, 0, 0))
    active_img.putpixel((5, 5), (102, 149, 201)) # closely matches 100, 150, 200
    res_active = cons.evaluate(active_img)
    assert res_active is None
    assert mock_input.tap_key.call_count == 0


def test_combat_priority_templates_directory_sorting() -> None:
    """CombatModule searches subdirectories (high_priority -> low_priority -> main) in order."""
    mock_input = MagicMock()
    rules = {
        "combat.enabled": "true",
        "combat.scanning_mode": "template",
        "combat.priority_enabled": "true",
        "combat.template_dir": "mock_templates",
        "combat.template_threshold": "0.8"
    }

    combat = CombatModule(rules, mock_input, hwnd=123)
    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    
    # Mock exists check on templates directories
    import numpy as np
    mock_tpl_img = np.zeros((10, 10, 3), dtype=np.uint8)
    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.glob", return_value=[Path("mock_templates/high_priority/boss.png")]), \
         patch("cv2.imread", return_value=mock_tpl_img) as mock_imread, \
         patch("cv2.matchTemplate", return_value=np.array([[0.9]], dtype=np.float32)) as mock_match, \
         patch("cv2.minMaxLoc", return_value=(0.0, 0.9, (0, 0), (10, 10))):
        
        target = combat.find_target(img)
        assert target is not None
        assert mock_imread.call_count >= 1


def test_color_filtered_looting_rarity() -> None:
    """LootModule scans target color centroid based on active rarity rules filter mode."""
    mock_input = MagicMock()
    
    rules = {
        "loot.enabled": "true",
        "loot.filter_mode": "rare_only",
        "loot.color.r": "200",
        "loot.color.g": "200",
        "loot.color.b": "200",
        "loot.color.tolerance": "10",
        "loot.rare_color.r": "255",
        "loot.rare_color.g": "0",
        "loot.rare_color.b": "0",
        "loot.rare_tolerance": "10",
        "loot.cooldown": "0.0",
        "loot.step_x": "1",
        "loot.step_y": "1"
    }

    loot = LootModule(rules, mock_input)

    # Image has only common item grey label pixels -> does not click
    common_img = Image.new("RGB", (10, 10), color=(200, 200, 200))
    res_common = loot.evaluate(common_img)
    assert res_common is None
    assert mock_input.click_mouse.call_count == 0

    # Image has rare red label pixels -> clicks centroid
    rare_img = Image.new("RGB", (10, 10), color=(0, 0, 0))
    rare_img.putpixel((5, 5), (255, 0, 0))
    res_rare = loot.evaluate(rare_img)
    assert res_rare is not None
    assert "rare_only" in res_rare
    assert mock_input.click_mouse.call_count == 1
