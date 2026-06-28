"""Consumables and Buffs Module for tracking timed actions."""

import time

from PIL import Image

from midgard.runtime.input import SCAN_CODES, BaseInputAdapter


class ConsumablesModule:
    """Manages recasting buffs and active consumables at defined duration intervals."""

    def __init__(self, rules: dict[str, str], input_adapter: BaseInputAdapter) -> None:
        self.rules = rules
        self.input_adapter = input_adapter

        # Load rules
        self.enabled = rules.get("consumables.enabled", "false").lower() == "true"
        self.items: list[tuple[str, str, float]] = []

        items_str = rules.get("consumables.items", "")
        self._parse_items(items_str)

        # State tracking: maps item name to float timestamp of last cast
        self.last_use_times: dict[str, float] = {}

        # Status Bar Icon Tracking variables (TASK-029)
        self.status_bar_enabled = rules.get("consumables.status_bar_enabled", "false").lower() == "true"
        self.status_check_x = int(rules.get("consumables.status_check_x", "50"))
        self.status_check_y = int(rules.get("consumables.status_check_y", "50"))
        self.status_color_r = int(rules.get("consumables.status_color_r", "255"))
        self.status_color_g = int(rules.get("consumables.status_color_g", "255"))
        self.status_color_b = int(rules.get("consumables.status_color_b", "255"))
        self.status_tolerance = int(rules.get("consumables.status_tolerance", "20"))

    def _parse_items(self, raw_str: str) -> None:
        """Parse consumables configuration string format 'name,key,dur;name,key,dur'."""
        if not raw_str:
            return
        segments = raw_str.split(";")
        for seg in segments:
            seg = seg.strip()
            if not seg:
                continue
            parts = seg.split(",")
            if len(parts) == 3:
                try:
                    name = parts[0].strip()
                    key = parts[1].strip()
                    duration = float(parts[2])
                    self.items.append((name, key, duration))
                except ValueError:
                    pass

    def evaluate(self, image: Image.Image) -> str | None:
        """Evaluate buff timers and recast the first expired buff."""
        if not self.enabled or not self.items:
            return None

        # Visual status bar active icon verification (TASK-029)
        if self.status_bar_enabled:
            w, h = image.size
            if self.status_check_x < w and self.status_check_y < h:
                r, g, b = image.getpixel((self.status_check_x, self.status_check_y))[:3]
                # If target status bar icon pixel matches the active color, we skip recasting
                if (abs(r - self.status_color_r) <= self.status_tolerance and
                        abs(g - self.status_color_g) <= self.status_tolerance and
                        abs(b - self.status_color_b) <= self.status_tolerance):
                    return None

        now = time.time()
        for item in self.items:
            name, key, duration = item
            last_cast = self.last_use_times.get(name, 0.0)

            # If duration elapsed (or never cast before), recast the buff
            if now - last_cast >= duration:
                scan_code = SCAN_CODES.get(key)
                if scan_code:
                    self.input_adapter.tap_key(scan_code)
                    self.last_use_times[name] = now
                    return (
                        f"Recasting buff '{name}' using key {key} "
                        f"(configured duration: {duration}s)."
                    )

        return None
