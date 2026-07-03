"""Heal Module for checking screen status bar crops and triggering healing keys."""

import random
import time
import numpy as np
from PIL import Image

from midgard.runtime.input import SCAN_CODES, BaseInputAdapter


def calculate_bar_percentage(crop_img: Image.Image) -> float:
    """Calculate the filled percentage of a status bar image using HSV color saturation.
    
    Tolerates short desaturated gaps (up to 6 pixels) to handle white/black overlaid text.
    """
    if crop_img.width <= 0 or crop_img.height <= 0:
        return 100.0

    # Convert to HSV to evaluate color saturation
    hsv_img = crop_img.convert("HSV")
    hsv_arr = np.array(hsv_img)
    h, w, c = hsv_arr.shape
    
    # We read along the vertical center row of the crop
    mid_y = h // 2
    if mid_y >= h:
        mid_y = h - 1

    # Extract saturation channel of the middle row
    # In HSV: channel 0 = Hue, channel 1 = Saturation, channel 2 = Value
    s_row = hsv_arr[mid_y, :, 1]
    
    filled_w = 0
    consecutive_empty = 0
    
    for x in range(w):
        sat = s_row[x]
        
        # Saturated color (blue/green/red/yellow) represents the active bar.
        # Desaturated gray/black/white represents empty background or overlaid text.
        is_colored = sat > 40
        
        if is_colored:
            filled_w = x + 1
            consecutive_empty = 0
        else:
            consecutive_empty += 1
            if consecutive_empty > 6:
                break
            filled_w = x + 1

    # Subtract the empty suffix if we broke out of the loop
    if consecutive_empty > 6:
        filled_w = max(0, filled_w - consecutive_empty)

    return (filled_w / w) * 100.0 if w > 0 else 100.0


class HealModule:
    """Monitors client area HP and SP status bars using color saturation to tap recovery hotkeys."""

    def __init__(self, rules: dict[str, str], input_adapter: BaseInputAdapter) -> None:
        self.rules = rules
        self.input_adapter = input_adapter
        self._last_use_time = 0.0

        # Load Heal Enabled Status
        self.enabled = rules.get("heal.enabled", "false").lower() == "true"

        # Cooldown management
        self.min_cooldown = float(rules.get("heal.min_cooldown", "0.5"))
        self.max_cooldown = float(rules.get("heal.max_cooldown", "0.8"))

        # HP Text Box Coordinates (X, Y, Width, Height)
        self.hp_threshold = float(rules.get("heal.hp_threshold", "70.0"))
        self.hp_x = int(rules.get("heal.hp_x", "100"))
        self.hp_y = int(rules.get("heal.hp_y", "50"))
        self.hp_w = int(rules.get("heal.hp_w", "60"))
        self.hp_h = int(rules.get("heal.hp_h", "12"))
        self.hp_key = rules.get("heal.hp_key", "F1")

        # SP Text Box Coordinates
        self.sp_enabled = rules.get("heal.sp_enabled", "false").lower() == "true"
        self.sp_threshold = float(rules.get("heal.sp_threshold", "50.0"))
        self.sp_x = int(rules.get("heal.sp_x", "100"))
        self.sp_y = int(rules.get("heal.sp_y", "66"))
        self.sp_w = int(rules.get("heal.sp_w", "60"))
        self.sp_h = int(rules.get("heal.sp_h", "12"))
        self.sp_key = rules.get("heal.sp_key", "F2")

    def evaluate(self, image: Image.Image) -> str | None:
        """Inspect crops for HP and SP color fill percentages, and trigger recovery keys."""
        if not self.enabled:
            return None

        # Check Global recovery delay cooldown
        now = time.time()
        if now - self._last_use_time < random.uniform(self.min_cooldown, self.max_cooldown):
            return None

        width, height = image.size

        # 1. EVALUATE HP
        if 0 <= self.hp_x < width and 0 <= self.hp_y < height:
            # Crop HP text segment bounding box
            crop_x2 = min(self.hp_x + self.hp_w, width)
            crop_y2 = min(self.hp_y + self.hp_h, height)
            hp_crop = image.crop((self.hp_x, self.hp_y, crop_x2, crop_y2))

            hp_pct = calculate_bar_percentage(hp_crop)

            if hp_pct < self.hp_threshold:
                scan_code = SCAN_CODES.get(self.hp_key)
                if scan_code:
                    self.input_adapter.tap_key(scan_code)
                    self._last_use_time = now
                    return (
                        f"HP trigger triggered ({hp_pct:.1f}% under {self.hp_threshold}%). "
                        f"Tapped {self.hp_key}."
                    )

        # 2. EVALUATE SP (Only if SP checking is enabled)
        if self.sp_enabled:
            if 0 <= self.sp_x < width and 0 <= self.sp_y < height:
                crop_x2 = min(self.sp_x + self.sp_w, width)
                crop_y2 = min(self.sp_y + self.sp_h, height)
                sp_crop = image.crop((self.sp_x, self.sp_y, crop_x2, crop_y2))

                sp_pct = calculate_bar_percentage(sp_crop)

                if sp_pct < self.sp_threshold:
                    scan_code = SCAN_CODES.get(self.sp_key)
                    if scan_code:
                        self.input_adapter.tap_key(scan_code)
                        self._last_use_time = now
                        return (
                            f"SP trigger triggered ({sp_pct:.1f}% under {self.sp_threshold}%). "
                            f"Tapped {self.sp_key}."
                        )

        return None
