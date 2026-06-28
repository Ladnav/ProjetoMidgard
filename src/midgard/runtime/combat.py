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
        """Scan the image using color centroid, template matching, or hover bar sweep."""
        mode = self.rules.get("combat.scanning_mode", "color")

        if mode == "template":
            return self._find_target_template(image)
        elif mode == "hover_bar":
            return self._find_target_hover_bar(image)
        else:
            return self._find_target_color(image)

    def _find_target_color(self, image: Image.Image) -> tuple[int, int] | None:
        """Scan using grid steps to locate color matching pixels and return centroid."""
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
            sum_x = sum(pt[0] for pt in matching_pixels)
            sum_y = sum(pt[1] for pt in matching_pixels)
            count = len(matching_pixels)
            return int(sum_x / count), int(sum_y / count)

        return None

    def _find_target_template(self, image: Image.Image) -> tuple[int, int] | None:
        """Search screen using OpenCV template matching for specific monster templates."""
        template_dir_str = self.rules.get("combat.template_dir", "")
        if not template_dir_str:
            return None

        from pathlib import Path
        import cv2
        import numpy as np
        
        template_dir = Path(template_dir_str)
        if not template_dir.exists():
            return None

        # Convert PIL to CV2 image
        img_np = np.array(image.convert("RGB"))
        img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

        priority_enabled = self.rules.get("combat.priority_enabled", "false").lower() == "true"
        
        # Build file list sorted by priority folders if enabled
        template_files = []
        if priority_enabled:
            high_pri_dir = template_dir / "high_priority"
            low_pri_dir = template_dir / "low_priority"
            
            if high_pri_dir.exists():
                template_files.extend(list(high_pri_dir.glob("*.png")))
            if low_pri_dir.exists():
                template_files.extend(list(low_pri_dir.glob("*.png")))
                
        # Append main folder files if any remaining or if priority is disabled
        main_files = [f for f in template_dir.glob("*.png") if f.name != "high_priority" and f.name != "low_priority"]
        template_files.extend(main_files)

        # Iterate templates in order
        for f in template_files:
            tpl = cv2.imread(str(f))
            if tpl is None:
                continue

            th = float(self.rules.get("combat.template_threshold", "0.8"))
            res = cv2.matchTemplate(img_cv, tpl, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

            if max_val >= th:
                # Target centroid calculation: top-left x,y plus half width/height
                h, w, _ = tpl.shape
                tx = max_loc[0] + w // 2
                ty = max_loc[1] + h // 2
                return tx, ty

        return None

    def _find_target_hover_bar(self, image: Image.Image) -> tuple[int, int] | None:
        """Move cursor in a grid pattern and inspect if red HP bar appears directly above."""
        width, height = image.size
        
        # Grid positions to sweep
        sweep_step_x = 80
        sweep_step_y = 60
        
        # Coordinates offsets for HP Bar checking relative to cursor
        offset_y = int(self.rules.get("combat.hover_offset_y", "-30"))
        box_w = int(self.rules.get("combat.hover_box_w", "40"))
        box_h = int(self.rules.get("combat.hover_box_h", "10"))
        
        # Color ranges of the red monster HP bar (default solid red)
        red_r = int(self.rules.get("combat.hover_red_r", "255"))
        red_g = int(self.rules.get("combat.hover_red_g", "0"))
        red_b = int(self.rules.get("combat.hover_red_b", "0"))
        tol = int(self.rules.get("combat.hover_tolerance", "25"))

        # Sweep screen coordinates
        for x in range(sweep_step_x, width - sweep_step_x, sweep_step_x):
            for y in range(sweep_step_y, height - sweep_step_y, sweep_step_y):
                # Briefly move mouse to sweep point
                self.input_adapter.move_mouse_relative(self.hwnd, x, y)
                time.sleep(0.02)  # 20ms quick sweep delay
                
                # Check target region above cursor coordinates
                check_x1 = max(0, x - box_w // 2)
                check_y1 = max(0, y + offset_y)
                check_x2 = min(width, check_x1 + box_w)
                check_y2 = min(height, check_y1 + box_h)
                
                crop = image.crop((check_x1, check_y1, check_x2, check_y2))
                crop_pixels = crop.load()
                
                red_hits = 0
                cw, ch = crop.size
                for cy in range(ch):
                    for cx in range(cw):
                        px = crop_pixels[cx, cy]
                        dr = abs(px[0] - red_r)
                        dg = abs(px[1] - red_g)
                        db = abs(px[2] - red_b)
                        if dr <= tol and dg <= tol and db <= tol:
                            red_hits += 1
                
                # If enough matching red pixels of the monster HP bar are found, target accepted!
                if red_hits >= 15:
                    return x, y

        return None
