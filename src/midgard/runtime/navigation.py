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

        # Execute A* step-by-step or direct walk action to current waypoint
        x, y, wait_time = self.waypoints[self.current_index]

        # Dynamic pathfinding option
        grid_map = self.rules.get("navigation.grid_map")
        # If grid_map rule is set, we run A* pathfinding.
        # Example format for grid_map: "10x10;0,0,0,0,0,0,0,0,0,0;..." or we parse a list of lists.
        # For simulation & testing, we accept navigation.grid_map representation
        path = None
        if grid_map:
            from midgard.runtime.pathfinding import AStarNavigator

            try:
                # Format: "width,height;row0;row1;..." where row is 0,1,0,...
                parts = grid_map.strip().split(";")
                w, h = map(int, parts[0].split(","))
                grid = []
                for row_str in parts[1:]:
                    if row_str.strip():
                        grid.append(list(map(int, row_str.strip().split(","))))

                # Assume start at last known click or 0,0 for routing simulation
                # We target (x, y) as grid coordinate
                navigator = AStarNavigator(grid)
                # Map coordinate to grid node (e.g. integer division/mapping if larger)
                start_node = (0, 0)
                end_node = (x, y)
                path = navigator.find_path(start_node, end_node)
            except Exception:
                pass

        if path and len(path) > 1:
            # Walk sequentially along the computed path steps
            for px, py in path[1:]:
                self.input_adapter.move_mouse_relative(self.hwnd, px, py)
                time.sleep(random.uniform(0.01, 0.03))
                self.input_adapter.click_mouse("left")
                time.sleep(random.uniform(0.05, 0.1))
            log_msg = (
                f"Navigation A* path traversal to coordinate ({x}, {y}) "
                f"completed via steps: {path[1:]}. "
                f"Waiting {wait_time}s for arrival."
            )
        else:
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
