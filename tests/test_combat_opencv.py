"""Tests for the advanced OpenCV combat target scanning algorithms."""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from PIL import Image

from midgard.runtime.combat import CombatModule


def test_combat_color_mode_centroid_calculation() -> None:
    """Color mode runs successfully calculating correct centroid coordinate targets."""
    mock_input = MagicMock()
    rules = {
        "combat.enabled": "true",
        "combat.scanning_mode": "color",
        "combat.target_r": "255",
        "combat.target_g": "0",
        "combat.target_b": "0",
        "combat.color_tolerance": "10",
        "combat.step_x": "2",
        "combat.step_y": "2",
        "combat.min_hits": "2",
        "combat.min_cooldown": "0.0",
        "combat.max_cooldown": "0.0",
    }
    combat = CombatModule(rules, mock_input, hwnd=123)

    img = Image.new("RGB", (20, 20), color=(0, 0, 0))
    img.putpixel((4, 4), (255, 0, 0))
    img.putpixel((6, 6), (255, 0, 0))

    target = combat.find_target(img)
    assert target == (5, 5)


def test_combat_template_mode_matching(tmp_path) -> None:
    """Template mode accurately matches visual templates using OpenCV matchTemplate."""
    mock_input = MagicMock()
    
    # Create a mock template png file in temporary folder
    tpl_dir = tmp_path / "monsters"
    tpl_dir.mkdir()
    tpl_path = tpl_dir / "poring.png"
    
    # Write a small template image
    tpl_img = Image.new("RGB", (5, 5), color=(255, 0, 0))
    tpl_img.save(tpl_path)

    rules = {
        "combat.enabled": "true",
        "combat.scanning_mode": "template",
        "combat.template_dir": str(tpl_dir),
        "combat.template_threshold": "0.8",
        "combat.min_cooldown": "0.0",
        "combat.max_cooldown": "0.0",
    }
    combat = CombatModule(rules, mock_input, hwnd=123)

    # Frame containing the template at top-left (0,0)
    frame = Image.new("RGB", (20, 20), color=(0, 0, 0))
    # Draw red square at top-left representing the template matching
    for x in range(5):
        for y in range(5):
            frame.putpixel((x, y), (255, 0, 0))

    tx, ty = combat.find_target(frame)
    # Centroid of (0,0) with 5x5 width/height is (2, 2)
    assert tx == 2
    assert ty == 2


def test_combat_hover_bar_mode_red_validation() -> None:
    """Hover HP bar validation scans coordinates sweeps and triggers on matching pixels."""
    mock_input = MagicMock()
    rules = {
        "combat.enabled": "true",
        "combat.scanning_mode": "hover_bar",
        "combat.hover_offset_y": "-5",
        "combat.hover_box_w": "10",
        "combat.hover_box_h": "4",
        "combat.hover_red_r": "255",
        "combat.hover_red_g": "0",
        "combat.hover_red_b": "0",
        "combat.hover_tolerance": "10",
        "combat.min_cooldown": "0.0",
        "combat.max_cooldown": "0.0",
    }
    combat = CombatModule(rules, mock_input, hwnd=123)

    # Generate game window screen frame containing monster hover bar red pixels
    # Grid sweeps at x = 80, y = 60
    # Offset of check box is centered on 80, y starts at y + offset_y = 60 - 5 = 55
    # Box spans x: [75, 85], y: [55, 59]
    frame = Image.new("RGB", (200, 200), color=(0, 0, 0))
    for x in range(75, 85):
        for y in range(55, 59):
            frame.putpixel((x, y), (255, 0, 0))

    target = combat.find_target(frame)
    assert target == (80, 60)
    assert mock_input.move_mouse_relative.call_count > 0
