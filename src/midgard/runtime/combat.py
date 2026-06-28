"""Combat Module for target selection and basic attack emulation."""

import random
import time

from PIL import Image

from midgard.runtime.input import BaseInputAdapter


class CombatModule:
    """Scans the screen capture for target colors (e.g. monster red nameplates) and clicks them."""

    def __init__(self, rules: dict[str, str], input_adapter: BaseInputAdapter, hwnd: int) -> None:
        self.rules = rules
        self.input_adapter = input_adapter
        self.hwnd = hwnd
        self._last_attack_time = 0.0

        # Load rules
        self.enabled = rules.get("combat.enabled", "false").lower() == "true"
        self.target_r = int(rules.get("combat.target_r", "255"))
        self.target_g = int(rules.get("combat.target_g", "0"))
        self.target_b = int(rules.get("combat.target_b", "0"))
        self.color_tolerance = int(rules.get("combat.color_tolerance", "30"))

        # Scanning steps for performance optimization
        self.step_x = int(rules.get("combat.step_x", "5"))
        self.step_y = int(rules.get("combat.step_y", "5"))
        self.min_hits = int(rules.get("combat.min_hits", "3"))

        # Delay cooldowns
        self.min_cooldown = float(rules.get("combat.min_cooldown", "1.0"))
        self.max_cooldown = float(rules.get("combat.max_cooldown", "2.0"))

    def evaluate(self, image: Image.Image) -> str | None:
        """Evaluate screen state, find target, and click to attack."""
        if not self.enabled:
            return None

        # Respect combat tick cooldown
        now = time.time()
        if now - self._last_attack_time < random.uniform(self.min_cooldown, self.max_cooldown):
            return None

        target_coords = self.find_target(image)
        if target_coords:
            tx, ty = target_coords
            # Move mouse and click target
            self.input_adapter.move_mouse_relative(self.hwnd, tx, ty)
            # Short sleep to let the mouse arrive before click (50ms - 100ms)
            time.sleep(random.uniform(0.05, 0.1))
            self.input_adapter.click_mouse("left")
            self._last_attack_time = now
            return f"Found combat target at ({tx}, {ty}). Clicked left button."

        return None

    def find_target(self, image: Image.Image) -> tuple[int, int] | None:
        """Scan the image using grid steps to locate target pixels, returning centroid."""
        width, height = image.size
        matching_pixels = []

        # Load pixel data buffer directly for speed
        pixels = image.load()

        for y in range(0, height, self.step_y):
            for x in range(0, width, self.step_x):
                pixel = pixels[x, y]
                r, g, b = pixel[0], pixel[1], pixel[2]

                distance = (
                    (r - self.target_r) ** 2 + (g - self.target_g) ** 2 + (b - self.target_b) ** 2
                ) ** 0.5

                if distance <= self.color_tolerance:
                    matching_pixels.append((x, y))

        if len(matching_pixels) >= self.min_hits:
            # Calculate centroid of matched pixel coordinates
            sum_x = sum(pt[0] for pt in matching_pixels)
            sum_y = sum(pt[1] for pt in matching_pixels)
            count = len(matching_pixels)
            return int(sum_x / count), int(sum_y / count)

        return None
