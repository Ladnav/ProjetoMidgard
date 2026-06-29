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

        # Multi-Map Transition Gates (TASK-030)
        self.current_map = rules.get("navigation.current_map", "prt_fild08")
        self.transition_enabled = rules.get("navigation.transition_enabled", "false").lower() == "true"
        
        # Transitions mapping: maps "from_map -> to_map" to (portal_x, portal_y, portal_wait_time)
        self.map_transitions = {}
        transitions_str = rules.get("navigation.transitions", "")
        self._parse_transitions(transitions_str)

        # Anti-Stuck Tracking (TASK-031)
        self.last_target_x = -1
        self.last_target_y = -1
        self.stuck_timestamp = 0.0
        self.stuck_timeout = 5.0  # seconds until stuck recovery triggers

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

    def _parse_transitions(self, raw_str: str) -> None:
        """Parse transitions string format 'from_map:to_map:x:y:wait;...'."""
        if not raw_str:
            return
        segments = raw_str.split(";")
        for seg in segments:
            seg = seg.strip()
            if not seg:
                continue
            parts = seg.split(":")
            if len(parts) == 5:
                try:
                    from_m = parts[0].strip()
                    to_m = parts[1].strip()
                    px = int(parts[2])
                    py = int(parts[3])
                    wait = float(parts[4])
                    self.map_transitions[f"{from_m}->{to_m}"] = (px, py, wait)
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

        # Stuck verification: Check if target waypoint coordinate matches the previous evaluated target (TASK-031)
        if x == self.last_target_x and y == self.last_target_y:
            if self.stuck_timestamp == 0.0:
                self.stuck_timestamp = now
            elif now - self.stuck_timestamp > self.stuck_timeout:
                # Character stuck threshold exceeded. Trigger A* recovery or skip index
                self.current_index = (self.current_index + 1) % len(self.waypoints)
                self.stuck_timestamp = 0.0
                return f"Navigation Stuck Recovery Triggered: Character coordinates staled for {self.stuck_timeout}s. Skipping to next waypoint."
        else:
            self.last_target_x = x
            self.last_target_y = y
            self.stuck_timestamp = 0.0

        # Multi-Map Transition Portal Interception (TASK-030)
        target_map = self.rules.get("navigation.target_map", self.current_map)
        if self.transition_enabled and target_map != self.current_map:
            # Check if there is a mapped transition to get closer to target map
            transition_key = f"{self.current_map}->{target_map}"
            if transition_key in self.map_transitions:
                tx, ty, t_wait = self.map_transitions[transition_key]
                self.input_adapter.move_mouse_relative(self.hwnd, tx, ty)
                time.sleep(random.uniform(0.05, 0.1))
                self.input_adapter.click_mouse("left")
                self.last_move_time = now
                self.current_wait_time = t_wait
                old_map = self.current_map
                self.current_map = target_map  # updates state simulating map loading completed
                return f"Multi-Map Transition: Traversed portal at ({tx}, {ty}) from {old_map} to {target_map}. Waiting {t_wait}s."

        # Dynamic pathfinding option
        grid_map = self.rules.get("navigation.grid_map")
        
        # Load map from image file path or JSON file path if specified (TASK-026)
        map_filepath = self.rules.get("navigation.map_file", "")
        path = None
        if map_filepath:
            from pathlib import Path
            import json
            p = Path(map_filepath)
            if p.exists():
                if p.suffix.lower() in (".png", ".bmp"):
                    try:
                        # Black pixels (0,0,0) are obstacles, non-black (255,255,255) are walkable
                        map_img = Image.open(p).convert("RGB")
                        w, h = map_img.size
                        grid = []
                        for r in range(h):
                            row = []
                            for c in range(w):
                                rgb = map_img.getpixel((c, r))
                                # std: 1 = walkable, 0 = obstacle
                                row.append(0 if rgb == (0, 0, 0) else 1)
                            grid.append(row)
                        from midgard.runtime.pathfinding import AStarNavigator
                        navigator = AStarNavigator(grid)
                        path = navigator.find_path((0, 0), (x, y))
                    except Exception:
                        pass
                elif p.suffix.lower() == ".json":
                    try:
                        with open(p, "r") as f:
                            grid = json.load(f)
                        from midgard.runtime.pathfinding import AStarNavigator
                        navigator = AStarNavigator(grid)
                        path = navigator.find_path((0, 0), (x, y))
                    except Exception:
                        pass

        if not path and grid_map:
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
                navigator = AStarNavigator(grid)
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
