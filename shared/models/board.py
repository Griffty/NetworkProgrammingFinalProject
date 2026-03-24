import math
from dataclasses import dataclass

Tile = tuple[int, int]
Point = tuple[float, float]


@dataclass(frozen=True, slots=True)
class BoardLayout:
    width: int
    height: int
    path_waypoints: tuple[Point, ...]
    path_tiles: frozenset[Tile]
    total_path_length_tiles: float
    spawn_tile: Tile
    leak_tile: Tile

    def contains_tile(self, tile_x: int, tile_y: int) -> bool:
        return 0 <= tile_x < self.width and 0 <= tile_y < self.height

    def is_path_tile(self, tile_x: int, tile_y: int) -> bool:
        return (tile_x, tile_y) in self.path_tiles

    def is_buildable_tile(self, tile_x: int, tile_y: int) -> bool:
        return self.contains_tile(tile_x, tile_y) and not self.is_path_tile(tile_x, tile_y)

    def position_for_distance(self, distance_tiles: float) -> Point:
        remaining_distance = max(0.0, min(distance_tiles, self.total_path_length_tiles))

        for start_point, end_point in zip(
            self.path_waypoints,
            self.path_waypoints[1:],
            strict=False,
        ):
            segment_length = math.dist(start_point, end_point)
            if remaining_distance <= segment_length:
                if segment_length == 0:
                    return end_point

                progress = remaining_distance / segment_length
                return (
                    start_point[0] + ((end_point[0] - start_point[0]) * progress),
                    start_point[1] + ((end_point[1] - start_point[1]) * progress),
                )
            remaining_distance -= segment_length

        return self.path_waypoints[-1]


def create_default_board_layout(width: int = 64, height: int = 64) -> BoardLayout:
    tile_waypoints = (
        (0, 12),
        (20, 12),
        (20, 36),
        (44, 36),
        (44, 18),
        (63, 18),
    )
    path_waypoints = tuple(_tile_center(tile_x, tile_y) for tile_x, tile_y in tile_waypoints)

    total_length = 0.0
    for start_point, end_point in zip(path_waypoints, path_waypoints[1:], strict=False):
        total_length += math.dist(start_point, end_point)

    return BoardLayout(
        width=width,
        height=height,
        path_waypoints=path_waypoints,
        path_tiles=frozenset(_build_path_tiles(tile_waypoints)),
        total_path_length_tiles=total_length,
        spawn_tile=tile_waypoints[0],
        leak_tile=tile_waypoints[-1],
    )

def _build_path_tiles(waypoints: tuple[Tile, ...]) -> set[Tile]:
    if len(waypoints) < 2:
        raise ValueError("A board path needs at least two waypoints.")

    path_tiles: set[Tile] = set()
    for start_tile, end_tile in zip(waypoints, waypoints[1:], strict=False):
        start_x, start_y = start_tile
        end_x, end_y = end_tile

        if start_x != end_x and start_y != end_y:
            raise ValueError("Board path segments must be axis-aligned.")

        if start_x == end_x:
            for tile_y in _inclusive_range(start_y, end_y):
                path_tiles.add((start_x, tile_y))
        else:
            for tile_x in _inclusive_range(start_x, end_x):
                path_tiles.add((tile_x, start_y))

    return path_tiles


def _inclusive_range(start_value: int, end_value: int) -> range:
    step = 1 if end_value >= start_value else -1
    return range(start_value, end_value + step, step)


def _tile_center(tile_x: int, tile_y: int) -> Point:
    return (tile_x + 0.5, tile_y + 0.5)


DEFAULT_BOARD_LAYOUT = create_default_board_layout()
