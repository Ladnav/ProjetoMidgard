"""Tests for polymorphic input generation, Discord webhook payloads, and restocking logic."""

import pytest
from unittest.mock import MagicMock, patch
from PIL import Image

from midgard.runtime.input import generate_bezier_path
from midgard.runtime.discord import DiscordNotifier
from midgard.runtime.stash import StashModule


def test_input_polymorphic_bezier_trajectories() -> None:
    """Polymorphic Bezier generator generates non-identical coordinate curves on successive runs."""
    start = (10, 10)
    end = (100, 100)
    
    path1 = generate_bezier_path(start, end, steps=10)
    path2 = generate_bezier_path(start, end, steps=10)
    
    # Path coordinates must differ slightly due to Gaussian micro-instability noise
    assert path1 != path2
    assert len(path1) == len(path2)
    assert path1[-1] == end  # final coordinate reaches target boundary
    assert path2[-1] == end


def test_discord_notifier_payload_dispatch() -> None:
    """DiscordNotifier constructs embeds payloads and sends HTTP requests to webhook."""
    rules = {
        "security.discord_webhook": "https://discord.com/api/webhooks/mock_id_123"
    }
    notifier = DiscordNotifier(rules)
    assert notifier.enabled is True

    # Mock urllib urlopen to prevent real outgoing internet connections
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.status = 204
        mock_urlopen.return_value.__enter__.return_value = mock_response

        success = notifier.send_notification("Test Alert message from Pytest!", level="WARNING")
        assert success is True
        assert mock_urlopen.call_count == 1


def test_stash_merchant_restocking_cycle() -> None:
    """StashModule executes Kafra storage deposit followed by merchant restock click actions."""
    mock_input = MagicMock()
    
    rules = {
        "stash.enabled": "true",
        "stash.restock_enabled": "true",
        "stash.teleport_hotkey": "F10",
        "stash.kafra_x": "300",
        "stash.kafra_y": "300",
        "stash.merchant_x": "450",
        "stash.merchant_y": "450",
        "stash.weight_check_x": "5",
        "stash.weight_check_y": "5",
        "stash.weight_color_r": "255",
        "stash.weight_color_g": "0",
        "stash.weight_color_b": "0",
        "stash.color_tolerance": "10",
    }

    stash = StashModule(rules, mock_input)
    assert stash.restock_enabled is True

    # 1. Trigger banking overload
    stash.last_check_time = 0.0
    img = Image.new("RGB", (20, 20), color=(0, 0, 0))
    img.putpixel((5, 5), (255, 0, 0))
    
    res = stash.evaluate(img, hwnd=123)
    assert stash.is_banking is True
    assert "Weight Overloaded" in res

    # 2. Execute banking & restocking step
    res_bank = stash.evaluate(img, hwnd=123)
    assert "restocking completed" in res_bank
    assert stash.is_banking is False
    # Check that mouse was clicked on Kafra NPC and then on merchant coordinates
    assert mock_input.click_mouse.call_count == 4
