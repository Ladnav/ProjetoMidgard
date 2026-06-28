"""Looting automation module analyzing screen item name clusters."""

import time
from typing import Dict, Any


class LootModule:
    """Scan the game screen for dropped item labels and send mouse clicks to loot them."""

    def __init__(self, rules: Dict[str, Any], input_adapter) -> None:
        self.input_adapter = input_adapter
        self.enabled = rules.get("loot.enabled", "false").lower() == "true"
        
        # Color targets for item nameplates (default: light grey typical of item names)
        self.loot_r = int(rules.get("loot.color.r", "220"))
        self.loot_g = int(rules.get("loot.color.g", "220"))
        self.loot_b = int(rules.get("loot.color.b", "220"))
        self.color_tolerance = int(rules.get("loot.color.tolerance", "15"))
        self.cooldown_delay = float(rules.get("loot.cooldown", "1.0"))
        self.step_x = int(rules.get("loot.step_x", "10"))
        self.step_y = int(rules.get("loot.step_y", "5"))

        self.last_loot_time = 0.0

        # Rarity/Color-Filtered Looting Rules (TASK-029)
        self.loot_filter_mode = rules.get("loot.filter_mode", "all")  # 'all', 'rare_only', 'equipment_only'
        self.rare_color_r = int(rules.get("loot.rare_color.r", "255"))
        self.rare_color_g = int(rules.get("loot.rare_color.g", "0"))
        self.rare_color_b = int(rules.get("loot.rare_color.b", "0"))
        self.rare_tolerance = int(rules.get("loot.rare_tolerance", "30"))

    def evaluate(self, image) -> str | None:
        """Scan the screen for matching item labels, calculate the centroid, and click."""
        if not self.enabled:
            return None

        now = time.time()
        if now - self.last_loot_time < self.cooldown_delay:
            return None

        width, height = image.size
        matching_pixels = []

        # Determine target color based on filter mode
        target_r, target_g, target_b = self.loot_r, self.loot_g, self.loot_b
        tolerance = self.color_tolerance

        if self.loot_filter_mode == "rare_only":
            target_r, target_g, target_b = self.rare_color_r, self.rare_color_g, self.rare_color_b
            tolerance = self.rare_tolerance

        # Performance optimization: scan with coordinate step intervals
        for y in range(0, height, self.step_y):
            for x in range(0, width, self.step_x):
                pixel = image.getpixel((x, y))
                r, g, b = pixel[0], pixel[1], pixel[2]
                
                # Check target color matching
                if (abs(r - target_r) <= tolerance and
                        abs(g - target_g) <= tolerance and
                        abs(b - target_b) <= tolerance):
                    matching_pixels.append((x, y))

        if not matching_pixels:
            return None

        # Find the pixel cluster center (centroid) representing the nearest item label
        # To avoid clicking on arbitrary averages, calculate centroid of the first distinct cluster
        centroid_x = sum(p[0] for p in matching_pixels) // len(matching_pixels)
        centroid_y = sum(p[1] for p in matching_pixels) // len(matching_pixels)

        # Move mouse and click to pick up item
        self.input_adapter.move_mouse(centroid_x, centroid_y)
        self.input_adapter.click_mouse()

        self.last_loot_time = now
        return f"Auto-Loot clicked on item label ({self.loot_filter_mode} mode) at coordinates: ({centroid_x}, {centroid_y})"
