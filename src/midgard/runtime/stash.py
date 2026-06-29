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
        
        # Restocking merchant rules (TASK-028)
        self.restock_enabled = rules.get("stash.restock_enabled", "false").lower() == "true"
        self.merchant_x = int(rules.get("stash.merchant_x", "400"))
        self.merchant_y = int(rules.get("stash.merchant_y", "400"))

        # NPC Selling rules (TASK-032)
        self.sell_enabled = rules.get("stash.sell_enabled", "false").lower() == "true"
        self.sell_npc_x = int(rules.get("stash.sell_npc_x", "500"))
        self.sell_npc_y = int(rules.get("stash.sell_npc_y", "500"))
        
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
        
        # Build composite log response based on restocking and selling triggers (TASK-032)
        log_responses = []
        
        # If restocking is enabled, trigger shop purchase movements after storage banking (TASK-028)
        restock_enabled = getattr(self, "restock_enabled", False)
        if restock_enabled:
            # Click the Merchant coordinates
            time.sleep(0.5)
            self.input_adapter.move_mouse_relative(hwnd, self.merchant_x, self.merchant_y)
            self.input_adapter.click_mouse("left")
            time.sleep(0.4)
            # Purchase items line click
            self.input_adapter.move_mouse_relative(hwnd, self.merchant_x, self.merchant_y + 40)
            self.input_adapter.click_mouse("left")
            log_responses.append(f"Restocked items at NPC merchant ({self.merchant_x}, {self.merchant_y})")

        # If selling is enabled, trigger NPC sell loops (TASK-032)
        sell_enabled = getattr(self, "sell_enabled", False)
        if sell_enabled:
            # Move cursor to sell NPC merchant coordinates
            time.sleep(0.5)
            self.input_adapter.move_mouse_relative(hwnd, self.sell_npc_x, self.sell_npc_y)
            self.input_adapter.click_mouse("left")
            time.sleep(0.4)
            # Click 'Sell items' option below
            self.input_adapter.move_mouse_relative(hwnd, self.sell_npc_x, self.sell_npc_y + 40)
            self.input_adapter.click_mouse("left")
            time.sleep(0.4)
            # Click inside trade window to confirm transaction
            self.input_adapter.move_mouse_relative(hwnd, self.sell_npc_x + 50, self.sell_npc_y + 80)
            self.input_adapter.click_mouse("left")
            log_responses.append(f"Sold junk items at NPC store ({self.sell_npc_x}, {self.sell_npc_y})")

        if log_responses:
            return f"Kafra banking cycle completed. Action loops executed: {'; '.join(log_responses)}. Resuming farming."

        return f"Kafra banking cycle completed at coordinates ({self.kafra_x}, {self.kafra_y}). Resuming farming."
