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
