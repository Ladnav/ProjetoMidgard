"""Auto-Stash / Inventory Weight Management Module."""

import time
from PIL import Image
from typing import Dict, Any


class StashModule:
    """Monitors client weight alerts and executes automated Kafra storage banking cycles."""

    def __init__(self, rules: Dict[str, Any], input_adapter) -> None:
        self.input_adapter = input_adapter
        self.enabled = rules.get("stash.enabled", "false").lower() == "true"
        
        self.teleport_hotkey = rules.get("stash.teleport_hotkey", "F12")
        self.kafra_x = int(rules.get("stash.kafra_x", "300"))
        self.kafra_y = int(rules.get("stash.kafra_y", "300"))
        
        # Color match coordinates for weight alert icon (e.g. balança laranja/vermelho)
        self.weight_check_x = int(rules.get("stash.weight_check_x", "600"))
        self.weight_check_y = int(rules.get("stash.weight_check_y", "50"))
        self.weight_color_r = int(rules.get("stash.weight_color_r", "255"))
        self.weight_color_g = int(rules.get("stash.weight_color_g", "120"))
        self.weight_color_b = int(rules.get("stash.weight_color_b", "0"))
        self.color_tolerance = int(rules.get("stash.color_tolerance", "30"))

        self.last_check_time = 0.0
        self.check_cooldown = 2.0  # Limit checking weight warning once every 2 seconds
        self.is_banking = False

    def evaluate(self, image: Image.Image, hwnd: int) -> str | None:
        """Scan game window for weight overload alerts and execute Kafra banking path triggers."""
        if not self.enabled:
            return None

        # If already banking, execute the storage dialog progression clicks
        if self.is_banking:
            return self._execute_banking_cycle(hwnd)

        now = time.time()
        if now - self.last_check_time < self.check_cooldown:
            return None
        self.last_check_time = now

        # Get color at configured weight check coordinate
        w, h = image.size
        if self.weight_check_x >= w or self.weight_check_y >= h:
            return None

        r, g, b = image.getpixel((self.weight_check_x, self.weight_check_y))[:3]
        
        # Check if color matches the orange/red weight alert balança warning
        if (abs(r - self.weight_color_r) <= self.color_tolerance and
                abs(g - self.weight_color_g) <= self.color_tolerance and
                abs(b - self.weight_color_b) <= self.color_tolerance):
            self.is_banking = True
            return self._start_banking(hwnd)

        return None

    def _start_banking(self, hwnd: int) -> str:
        """Trigger recall teleport to town to initiate Kafra storage banking."""
        # Use Butterfly Wing teleport hotkey
        self.input_adapter.tap_key(self.teleport_hotkey)
        return f"Weight Overloaded! Triggered town teleport hotkey '{self.teleport_hotkey}' to initiate Kafra banking."

    def _execute_banking_cycle(self, hwnd: int) -> str:
        """Move cursor to Kafra coordinates and click to deposit items."""
        # Click the Kafra NPC coordinates
        self.input_adapter.move_mouse_relative(hwnd, self.kafra_x, self.kafra_y)
        time.sleep(0.1)
        self.input_adapter.click_mouse("left")
        
        # Simulate selecting storage dialog options by clicking down
        time.sleep(0.3)
        self.input_adapter.move_mouse_relative(hwnd, self.kafra_x, self.kafra_y + 40)
        self.input_adapter.click_mouse("left")

        # Cycle finished: clear weight block state
        self.is_banking = False
        return f"Kafra banking cycle completed at coordinates ({self.kafra_x}, {self.kafra_y}). Resuming farming."
