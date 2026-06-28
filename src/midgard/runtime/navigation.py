"""Waypoint Navigation Module for moving character along coordinate paths."""

import random
import time

from PIL import Image

from midgard.runtime.input import BaseInputAdapter


class NavigationModule:
    """Moves the mouse and clicks coordinates sequentially to navigate the character."""

    def __init__(self, rules: dict[str, str], input_adapter: BaseInputAdapter, hwnd: int) -> None:
        self.rules = rules
        self.input_adapter = input_adapter
        self.hwnd = hwnd

        # Load rules
        self.enabled = rules.get("navigation.enabled", "false").lower() == "true"
        self.waypoints: list[tuple[int, int, float]] = []

        waypoints_str = rules.get("navigation.waypoints", "")
        self._parse_waypoints(waypoints_str)

        # State tracking
        self.current_index = 0
        self.last_move_time = 0.0
        self.current_wait_time = 0.0

    def _parse_waypoints(self, raw_str: str) -> None:
        """Parse waypoint configuration string of format 'x,y,wait;x,y,wait'."""
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
                    x = int(parts[0])
                    y = int(parts[1])
                    wait = float(parts[2])
                    self.waypoints.append((x, y, wait))
                except ValueError:
                    pass

    def evaluate(self, image: Image.Image) -> str | None:
        """Evaluate path progress and click next waypoint if arrival timer expired."""
        if not self.enabled or not self.waypoints:
            return None

        now = time.time()
        # Still walking/waiting for previous waypoint
        if now - self.last_move_time < self.current_wait_time:
            return None

        # Execute walk action to current waypoint
        x, y, wait_time = self.waypoints[self.current_index]
        self.input_adapter.move_mouse_relative(self.hwnd, x, y)
        time.sleep(random.uniform(0.05, 0.1))
        self.input_adapter.click_mouse("left")

        log_msg = (
            f"Navigation click at coordinate ({x}, {y}) for waypoint index "
            f"{self.current_index}. Waiting {wait_time}s for arrival."
        )

        # Update timers and cycle waypoint index
        self.last_move_time = now
        self.current_wait_time = wait_time
        self.current_index = (self.current_index + 1) % len(self.waypoints)

        return log_msg
