"""Emergency Evasion Module for saving the character during high danger states."""

import random
import time

from midgard.runtime.input import SCAN_CODES, BaseInputAdapter


class EvasionModule:
    """Monitors health state and triggers emergency hotkeys under critical threat."""

    def __init__(self, rules: dict[str, str], input_adapter: BaseInputAdapter) -> None:
        self.rules = rules
        self.input_adapter = input_adapter
        self._last_use_time = 0.0

        # Load configurations
        self.enabled = rules.get("evasion.enabled", "false").lower() == "true"
        self.panic_hp_threshold = float(rules.get("evasion.panic_hp_threshold", "20.0"))
        self.evasion_key = rules.get("evasion.key", "F9")
        self.min_cooldown = float(rules.get("evasion.min_cooldown", "1.0"))
        self.max_cooldown = float(rules.get("evasion.max_cooldown", "2.0"))

    def evaluate_hp(self, hp_pct: float) -> str | None:
        """Evaluate danger threat level based on current HP percentage."""
        if not self.enabled:
            return None

        # Check cooldown
        now = time.time()
        if now - self._last_use_time < random.uniform(self.min_cooldown, self.max_cooldown):
            return None

        if hp_pct <= self.panic_hp_threshold:
            scan_code = SCAN_CODES.get(self.evasion_key)
            if scan_code:
                self.input_adapter.tap_key(scan_code)
                self._last_use_time = now
                return (
                    f"CRITICAL: HP dropped to {hp_pct}%. "
                    f"Triggered emergency evasion key {self.evasion_key}!"
                )

        return None
