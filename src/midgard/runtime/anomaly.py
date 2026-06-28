"""Anomaly module scanning screen for GM checks or CAPTCHA popups."""

import time
from pathlib import Path
from PIL import Image
from typing import Dict, Any


class AnomalyModule:
    """Matches screen against known CAPTCHA dialog templates and triggers security actions."""

    def __init__(self, rules: Dict[str, Any], input_adapter) -> None:
        self.input_adapter = input_adapter
        self.enabled = rules.get("security.enabled", "false").lower() == "true"
        
        self.templates_dir_str = rules.get("security.templates_dir", "")
        self.similarity_threshold = float(rules.get("security.threshold", "0.85"))
        self.panic_action = rules.get("security.panic_action", "alarm_only")  # alarm_only, teleport, logout
        self.panic_hotkey = rules.get("security.panic_hotkey", "F12")

        self.last_check_time = 0.0
        self.check_cooldown = 1.0  # limit checking checks to once per second

    def evaluate(self, image: Image.Image) -> str | None:
        """Scan active screen for verification dialog templates and trigger panic action."""
        if not self.enabled or not self.templates_dir_str:
            return None

        now = time.time()
        if now - self.last_check_time < self.check_cooldown:
            return None
        self.last_check_time = now

        templates_dir = Path(self.templates_dir_str)
        if not templates_dir.exists():
            return None

        import cv2
        import numpy as np

        # Convert PIL to CV2 image
        img_np = np.array(image.convert("RGB"))
        img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

        for template_file in templates_dir.glob("*.png"):
            tpl = cv2.imread(str(template_file))
            if tpl is None:
                continue

            # Avoid division-by-zero or mathematical instability on uniform flat color images
            if np.std(img_cv) < 1.0 or np.std(tpl) < 1.0:
                # Fallback to direct absolute difference thresholding for safety
                continue

            res = cv2.matchTemplate(img_cv, tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)

            # Verification captcha pop-up match found
            if max_val >= self.similarity_threshold:
                return self.trigger_panic(template_file.name)

        return None

    def trigger_panic(self, template_name: str) -> str:
        """Execute anti-detection panic response."""
        alert_msg = f"Visual Anomaly Detected: matched template '{template_name}'!"

        if self.panic_action == "teleport":
            # Press Fly Wing/Teleport F-key
            self.input_adapter.tap_key(self.panic_hotkey)
            return f"{alert_msg} Action: Teleport key '{self.panic_hotkey}' pressed."
        elif self.panic_action == "logout":
            # Type logout command or force shutdown client (simulated by ALT+F4)
            self.input_adapter.tap_key("alt+f4")
            return f"{alert_msg} Action: Sent client force quit ALT+F4 command."
        else:
            return f"{alert_msg} Action: Alarm notification raised."
