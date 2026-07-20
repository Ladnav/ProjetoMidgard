"""Looting automation module analyzing screen item name clusters."""

import time
from typing import Any

Point = tuple[int, int]


def cluster_points(points: list[Point], radius: int) -> list[list[Point]]:
    """Group nearby points into connected clusters.

    Two points belong to the same cluster when they are within ``radius`` on both
    axes, transitively. Uses spatial bucketing so the scan stays linear in
    practice instead of comparing every pair.
    """
    if not points:
        return []

    cell = max(1, radius)
    buckets: dict[tuple[int, int], list[Point]] = {}
    for p in points:
        buckets.setdefault((p[0] // cell, p[1] // cell), []).append(p)

    seen: set[Point] = set()
    clusters: list[list[Point]] = []

    for origin in points:
        if origin in seen:
            continue
        seen.add(origin)
        queue = [origin]
        component: list[Point] = []
        while queue:
            current = queue.pop()
            component.append(current)
            bx, by = current[0] // cell, current[1] // cell
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for candidate in buckets.get((bx + dx, by + dy), ()):
                        if candidate in seen:
                            continue
                        if (
                            abs(candidate[0] - current[0]) <= radius
                            and abs(candidate[1] - current[1]) <= radius
                        ):
                            seen.add(candidate)
                            queue.append(candidate)
        clusters.append(component)

    return clusters


class LootModule:
    """Scan the game screen for dropped item labels and send mouse clicks to loot them."""

    def __init__(self, rules: dict[str, Any], input_adapter) -> None:
        self.input_adapter = input_adapter
        self.enabled = rules.get("loot.enabled", "false").lower() == "true"

        # Color targets for item nameplates (default: light grey typical of item names)
        self.loot_r = int(rules.get("loot.color.r", "220"))
        self.loot_g = int(rules.get("loot.color.g", "220"))
        self.loot_b = int(rules.get("loot.color.b", "220"))
        self.color_tolerance = int(rules.get("loot.color.tolerance", "15"))
        self.cooldown_delay = float(rules.get("loot.cooldown", "1.0"))
        self.step_x = int(rules.get("loot.step_x", "10"))
        self.step_y = int(rules.get("loot.step_y", "5"))

        self.last_loot_time = 0.0

        # Rarity/Color-Filtered Looting Rules (TASK-029)
        self.loot_filter_mode = rules.get(
            "loot.filter_mode", "all"
        )  # 'all', 'rare_only', 'equipment_only'
        self.rare_color_r = int(rules.get("loot.rare_color.r", "255"))
        self.rare_color_g = int(rules.get("loot.rare_color.g", "0"))
        self.rare_color_b = int(rules.get("loot.rare_color.b", "0"))
        self.rare_tolerance = int(rules.get("loot.rare_tolerance", "30"))

        # Clustering: separate distinct item labels instead of averaging the whole
        # screen into a single meaningless midpoint.
        default_radius = max(self.step_x, self.step_y) * 3
        self.cluster_radius = int(rules.get("loot.cluster_radius", str(default_radius)))
        # Defaults to 1 so a small or faint label still counts; raise it to discard
        # isolated stray pixels as noise.
        self.min_cluster_size = int(rules.get("loot.min_cluster_size", "1"))

        # Reference point used to choose the closest label. Defaults to the image
        # centre, where the controlled character stands in most clients.
        origin_x = rules.get("loot.origin_x", "")
        origin_y = rules.get("loot.origin_y", "")
        self.origin_x = int(origin_x) if str(origin_x).strip() else None
        self.origin_y = int(origin_y) if str(origin_y).strip() else None

    def evaluate(self, image) -> str | None:
        """Scan for item labels, cluster them, and click the closest distinct label."""
        if not self.enabled:
            return None

        now = time.time()
        if now - self.last_loot_time < self.cooldown_delay:
            return None

        width, height = image.size

        # Determine target color based on filter mode
        target_r, target_g, target_b = self.loot_r, self.loot_g, self.loot_b
        tolerance = self.color_tolerance

        if self.loot_filter_mode == "rare_only":
            target_r, target_g, target_b = (
                self.rare_color_r,
                self.rare_color_g,
                self.rare_color_b,
            )
            tolerance = self.rare_tolerance

        # Performance optimization: scan with coordinate step intervals
        matching_pixels: list[Point] = []
        for y in range(0, height, self.step_y):
            for x in range(0, width, self.step_x):
                pixel = image.getpixel((x, y))
                r, g, b = pixel[0], pixel[1], pixel[2]

                if (
                    abs(r - target_r) <= tolerance
                    and abs(g - target_g) <= tolerance
                    and abs(b - target_b) <= tolerance
                ):
                    matching_pixels.append((x, y))

        if not matching_pixels:
            return None

        # Group the matches into distinct labels. Averaging every match together
        # would aim at empty ground whenever two items lie on opposite sides.
        clusters = cluster_points(matching_pixels, self.cluster_radius)
        clusters = [c for c in clusters if len(c) >= self.min_cluster_size]
        if not clusters:
            return None

        origin_x = self.origin_x if self.origin_x is not None else width // 2
        origin_y = self.origin_y if self.origin_y is not None else height // 2

        def centroid(cluster: list[Point]) -> Point:
            return (
                sum(p[0] for p in cluster) // len(cluster),
                sum(p[1] for p in cluster) // len(cluster),
            )

        # Pick the label closest to the character rather than an arbitrary one.
        def distance_to_origin(cluster: list[Point]) -> int:
            cx, cy = centroid(cluster)
            return (cx - origin_x) ** 2 + (cy - origin_y) ** 2

        best_cluster = min(clusters, key=distance_to_origin)
        centroid_x, centroid_y = centroid(best_cluster)

        # Move mouse and click to pick up item
        self.input_adapter.move_mouse(centroid_x, centroid_y)
        self.input_adapter.click_mouse()

        self.last_loot_time = now
        return (
            f"Auto-Loot clicked on item label ({self.loot_filter_mode} mode) "
            f"at coordinates: ({centroid_x}, {centroid_y}) "
            f"[{len(clusters)} label(s) detected, closest picked]"
        )
