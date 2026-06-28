"""Heal Module for checking screen state and triggering healing keys."""

import random
import time

from PIL import Image

from midgard.runtime.input import SCAN_CODES, BaseInputAdapter


class HealModule:
    """Monitors client area pixel colors to determine low HP/SP state and tap hotkeys."""

    def __init__(self, rules: dict[str, str], input_adapter: BaseInputAdapter) -> None:
        self.rules = rules
        self.input_adapter = input_adapter
        self._last_use_time = 0.0

        # Load configuration parameters
        self.enabled = rules.get("heal.enabled", "false").lower() == "true"
        self.hp_threshold = float(rules.get("heal.hp_threshold", "70.0"))
        self.hp_x = int(rules.get("heal.hp_x", "100"))
        self.hp_y = int(rules.get("heal.hp_y", "50"))
        self.hp_key = rules.get("heal.hp_key", "F1")

        # Color boundaries
        # Expected RGB color of HP bar (e.g. green).
        # Deviating from this color suggests HP is below this coordinate.
        self.expected_hp_r = int(rules.get("heal.expected_hp_r", "0"))
        self.expected_hp_g = int(rules.get("heal.expected_hp_g", "255"))
        self.expected_hp_b = int(rules.get("heal.expected_hp_b", "0"))
        self.color_tolerance = int(rules.get("heal.color_tolerance", "30"))

        # Cooldown management
        self.min_cooldown = float(rules.get("heal.min_cooldown", "0.5"))
        self.max_cooldown = float(rules.get("heal.max_cooldown", "0.8"))

    def evaluate(self, image: Image.Image) -> str | None:
        """Inspect the health status pixel coordinate in the provided screen capture.

        Taps the heal key if low health state is detected, respecting random cooldown delays.
        Returns a log message string if triggered, else None.
        """
        if not self.enabled:
            return None

        # Verify pixel bounds
        width, height = image.size
        if not (0 <= self.hp_x < width and 0 <= self.hp_y < height):
            return f"Heal coordinates ({self.hp_x}, {self.hp_y}) out of bounds ({width}x{height})"

        # Check cooldown
        now = time.time()
        if now - self._last_use_time < random.uniform(self.min_cooldown, self.max_cooldown):
            return None

        # Read RGB color at trigger point
        pixel = image.getpixel((self.hp_x, self.hp_y))
        r, g, b = pixel[0], pixel[1], pixel[2]

        # Calculate Euclidean color distance
        distance = (
            (r - self.expected_hp_r) ** 2
            + (g - self.expected_hp_g) ** 2
            + (b - self.expected_hp_b) ** 2
        ) ** 0.5

        # If color distance exceeds tolerance, health is missing at this point
        if distance > self.color_tolerance:
            scan_code = SCAN_CODES.get(self.hp_key)
            if scan_code:
                self.input_adapter.tap_key(scan_code)
                self._last_use_time = now
                return (
                    f"HP trigger coordinate ({self.hp_x}, {self.hp_y}) "
                    f"color was {pixel}. Triggered {self.hp_key}."
                )

        return None
