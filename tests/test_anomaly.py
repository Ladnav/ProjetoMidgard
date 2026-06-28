"""Tests for visual anomaly CAPTCHA checks and security panic responses."""

import pytest
from unittest.mock import MagicMock
from pathlib import Path
from PIL import Image

from midgard.runtime.anomaly import AnomalyModule


def test_anomaly_alarm_response_on_matched_popup(tmp_path) -> None:
    """AnomalyModule matches visual popups and triggers specified panic actions."""
    mock_input = MagicMock()
    
    # Create template file representating popup verification dialog
    tpl_dir = tmp_path / "security"
    tpl_dir.mkdir()
    tpl_file = tpl_dir / "captcha_verify.png"
    
    # Write a template image with visual contrast (standard deviation > 1.0)
    tpl_img = Image.new("RGB", (6, 6), color=(0, 0, 0))
    # Draw checkered pattern
    for x in range(0, 6, 2):
        for y in range(0, 6, 2):
            tpl_img.save(tpl_file)
            tpl_img.putpixel((x, y), (255, 255, 255))
    tpl_img.save(tpl_file)

    rules = {
        "security.enabled": "true",
        "security.templates_dir": str(tpl_dir),
        "security.threshold": "0.8",
        "security.panic_action": "teleport",
        "security.panic_hotkey": "F9",
    }
    
    anomaly = AnomalyModule(rules, mock_input)

    # 1. Evaluate clean frame with contrast (but not matching the template) -> no trigger
    clean_frame = Image.new("RGB", (20, 20), color=(0, 0, 0))
    for i in range(10):
        clean_frame.putpixel((i, i), (10, 10, 10))
    res = anomaly.evaluate(clean_frame)
    assert res is None
    assert mock_input.tap_key.call_count == 0

    # 2. Reset evaluation delay and test matching frame containing template popup
    anomaly.last_check_time = 0.0
    matching_frame = Image.new("RGB", (20, 20), color=(0, 0, 0))
    # Checkered pattern drawn on matching frame
    for x in range(0, 6, 2):
        for y in range(0, 6, 2):
            matching_frame.putpixel((x, y), (255, 255, 255))

    res = anomaly.evaluate(matching_frame)
    assert res is not None
    assert "Visual Anomaly Detected" in res
    # Checked that panic teleport hotkey was tapped
    mock_input.tap_key.assert_called_with("F9")
