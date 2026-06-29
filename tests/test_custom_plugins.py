"""Tests for compiling and execution of custom script plugins in NavigationModule."""

import pytest
from unittest.mock import MagicMock
from PIL import Image

from midgard.runtime.navigation import NavigationModule


def test_custom_script_plugin_compilation_and_execution(tmp_path) -> None:
    """NavigationModule loads and runs evaluate script hooks from python plugins dynamically."""
    plugin_file = tmp_path / "custom_anti_trap.py"
    
    # Write a simple custom python plugin script with standard run_script entry hook
    script_code = """
def run_script(image, input_adapter, hwnd):
    # Perform custom check action
    input_adapter.tap_key("F10")
    return "Anti-trap activated"
"""
    with open(plugin_file, "w") as f:
        f.write(script_code)

    mock_input = MagicMock()
    rules = {
        "navigation.enabled": "true",
        "navigation.waypoints": "100,100,2.0",
        "navigation.custom_script": str(plugin_file),
    }

    nav = NavigationModule(rules, mock_input, hwnd=123)
    assert nav.custom_plugin_module is not None

    img = Image.new("RGB", (20, 20), color=(0, 0, 0))
    res = nav.evaluate(img)
    
    # Verify that mock input adapter was clicked by custom script hook
    assert res == "Custom Script Executed: Anti-trap activated"
    mock_input.tap_key.assert_called_with("F10")
