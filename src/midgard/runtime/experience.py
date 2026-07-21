"""Experience tracking module reading the on-screen EXP counter via OCR.

The runtime cannot observe experience directly, so the tracker samples a
user-configured screen region, resolves the number with the pixel-font digit
recognizer, and accumulates the positive deltas between readings.
"""

import time
from typing import Any

from midgard.vision.ocr import DigitRecognizer


class ExperienceTracker:
    """Accumulate experience gained by watching a numeric EXP region on screen."""

    def __init__(self, rules: dict[str, Any], recognizer: DigitRecognizer | None = None) -> None:
        self.enabled = rules.get("experience.enabled", "false").lower() == "true"
        self.region_x = int(rules.get("experience.x", "0"))
        self.region_y = int(rules.get("experience.y", "0"))
        self.region_w = int(rules.get("experience.w", "120"))
        self.region_h = int(rules.get("experience.h", "16"))

        # OCR is comparatively expensive; sample on an interval rather than every tick.
        self.interval = float(rules.get("experience.interval", "2.0"))

        # Guard against OCR misreads producing absurd one-shot jumps. A reading
        # that gains more than this in a single sample is treated as noise and
        # only re-baselines the tracker. Zero disables the guard.
        self.max_delta = int(rules.get("experience.max_delta", "0"))

        self.recognizer = recognizer or DigitRecognizer()

        self.total_gained = 0
        self.last_value: int | None = None
        self.last_read_time = 0.0
        self.level_ups = 0

    def read_value(self, image) -> int | None:
        """Crop the configured region and resolve it to an integer, or None."""
        width, height = image.size
        x1 = max(0, self.region_x)
        y1 = max(0, self.region_y)
        x2 = min(x1 + self.region_w, width)
        y2 = min(y1 + self.region_h, height)
        if x2 <= x1 or y2 <= y1:
            return None

        crop = image.crop((x1, y1, x2, y2))
        text = self.recognizer.parse_image(crop)
        digits = "".join(c for c in text if c.isdigit())
        if not digits:
            return None
        try:
            return int(digits)
        except ValueError:
            return None

    def evaluate(self, image) -> str | None:
        """Sample the EXP region and accumulate the gain since the last reading."""
        if not self.enabled:
            return None

        now = time.time()
        if now - self.last_read_time < self.interval:
            return None
        self.last_read_time = now

        value = self.read_value(image)
        if value is None:
            return None

        previous = self.last_value
        self.last_value = value

        # First successful reading only establishes the baseline.
        if previous is None:
            return None

        delta = value - previous
        if delta == 0:
            return None

        if delta < 0:
            # EXP counters reset on level up (and when switching to a percentage
            # display). Re-baseline instead of recording a negative gain.
            self.level_ups += 1
            return f"Experience counter reset (level up?): {previous} -> {value}"

        if self.max_delta > 0 and delta > self.max_delta:
            # Implausible jump: most likely an OCR misread, so drop it.
            return f"Ignored implausible EXP jump of {delta} (max {self.max_delta})"

        self.total_gained += delta
        return f"Experience gained: +{delta} (session total: {self.total_gained})"
