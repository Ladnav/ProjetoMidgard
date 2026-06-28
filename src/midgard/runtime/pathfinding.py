"""Grid-based A* Pathfinding Algorithm for obstacle avoidance."""

import heapq


class AStarNavigator:
    """Computes the shortest path on a 2D grid avoiding obstacles."""

    def __init__(self, grid: list[list[int]]) -> None:
        """Initialize with a 2D grid where 0 is walkable and 1 is blocked."""
        self.grid = grid
        self.height = len(grid)
        self.width = len(grid[0]) if self.height > 0 else 0

    def _heuristic(self, a: tuple[int, int], b: tuple[int, int]) -> float:
        """Manhattan distance heuristic."""
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def find_path(
        self, start: tuple[int, int], end: tuple[int, int]
    ) -> list[tuple[int, int]] | None:
        """Find the shortest path from start to end coordinate.

        Returns a list of steps including start and end, or None if no path exists.
        """
        if not (0 <= start[0] < self.width and 0 <= start[1] < self.height):
            return None
        if not (0 <= end[0] < self.width and 0 <= end[1] < self.height):
            return None
        if self.grid[start[1]][start[0]] == 1 or self.grid[end[1]][end[0]] == 1:
            return None

        open_set = []
        heapq.heappush(open_set, (0.0, start))
        came_from = {}
        g_score = {start: 0.0}
        f_score = {start: self._heuristic(start, end)}

        while open_set:
            _, current = heapq.heappop(open_set)

            if current == end:
                # Reconstruct path
                path = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                path.reverse()
                return path

            # 4-directional movement (up, down, left, right)
            neighbors = [
                (current[0] + 1, current[1]),
                (current[0] - 1, current[1]),
                (current[0], current[1] + 1),
                (current[0], current[1] - 1),
            ]

            for neighbor in neighbors:
                nx, ny = neighbor
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    if self.grid[ny][nx] == 1:
                        continue

                    tentative_g = g_score[current] + 1.0
                    if neighbor not in g_score or tentative_g < g_score[neighbor]:
                        came_from[neighbor] = current
                        g_score[neighbor] = tentative_g
                        f = tentative_g + self._heuristic(neighbor, end)
                        f_score[neighbor] = f
                        heapq.heappush(open_set, (f, neighbor))

        return None
