from __future__ import annotations

import math

Point = dict[str, float]

EPSILON = 1e-9


def distance(a: Point, b: Point) -> float:
    return math.hypot(b["x"] - a["x"], b["y"] - a["y"])


def _dedupe_points(points: list[Point]) -> list[Point]:
    unique: list[Point] = []
    for point in points:
        if any(distance(point, existing) <= 1e-6 for existing in unique):
            continue
        unique.append(point)
    return unique


def _orientation(a: Point, b: Point, c: Point) -> float:
    return (b["x"] - a["x"]) * (c["y"] - a["y"]) - (b["y"] - a["y"]) * (c["x"] - a["x"])


def _on_segment(a: Point, b: Point, c: Point) -> bool:
    return (
        min(a["x"], c["x"]) - EPSILON <= b["x"] <= max(a["x"], c["x"]) + EPSILON
        and min(a["y"], c["y"]) - EPSILON <= b["y"] <= max(a["y"], c["y"]) + EPSILON
        and abs(_orientation(a, b, c)) <= EPSILON
    )


def segments_intersect(a1: Point, a2: Point, b1: Point, b2: Point) -> bool:
    o1 = _orientation(a1, a2, b1)
    o2 = _orientation(a1, a2, b2)
    o3 = _orientation(b1, b2, a1)
    o4 = _orientation(b1, b2, a2)

    if abs(o1) <= EPSILON and _on_segment(a1, b1, a2):
        return True
    if abs(o2) <= EPSILON and _on_segment(a1, b2, a2):
        return True
    if abs(o3) <= EPSILON and _on_segment(b1, a1, b2):
        return True
    if abs(o4) <= EPSILON and _on_segment(b1, a2, b2):
        return True

    return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)


def segment_position(point: Point, p1: Point, p2: Point) -> float:
    dx = p2["x"] - p1["x"]
    dy = p2["y"] - p1["y"]
    length_sq = dx * dx + dy * dy
    if length_sq <= EPSILON:
        return 0.0
    position = ((point["x"] - p1["x"]) * dx + (point["y"] - p1["y"]) * dy) / length_sq
    return max(0.0, min(1.0, position))


def point_on_segment_at(p1: Point, p2: Point, position: float) -> Point:
    clamped = max(0.0, min(1.0, position))
    return {
        "x": p1["x"] + (p2["x"] - p1["x"]) * clamped,
        "y": p1["y"] + (p2["y"] - p1["y"]) * clamped,
    }


def project_point_to_segment(point: Point, p1: Point, p2: Point) -> Point:
    return point_on_segment_at(p1, p2, segment_position(point, p1, p2))


def segment_intersection_point(a1: Point, a2: Point, b1: Point, b2: Point) -> Point | None:
    if not segments_intersect(a1, a2, b1, b2):
        return None

    ax = a2["x"] - a1["x"]
    ay = a2["y"] - a1["y"]
    bx = b2["x"] - b1["x"]
    by = b2["y"] - b1["y"]
    denominator = ax * by - ay * bx

    if abs(denominator) <= EPSILON:
        overlap_points = []
        for point in (a1, a2):
            if _on_segment(b1, point, b2):
                overlap_points.append(point)
        for point in (b1, b2):
            if _on_segment(a1, point, a2):
                overlap_points.append(point)
        overlap_points = _dedupe_points(overlap_points)
        if not overlap_points:
            return None
        position = sum(segment_position(point, a1, a2) for point in overlap_points) / len(overlap_points)
        return point_on_segment_at(a1, a2, position)

    t = ((b1["x"] - a1["x"]) * by - (b1["y"] - a1["y"]) * bx) / denominator
    return point_on_segment_at(a1, a2, t)


def segment_polygon_intersection_points(p1: Point, p2: Point, polygon: list[Point]) -> list[Point]:
    if len(polygon) < 3:
        return []

    points: list[Point] = []
    if point_in_polygon(p1, polygon):
        points.append(p1)
    if point_in_polygon(p2, polygon):
        points.append(p2)

    for index, current in enumerate(polygon):
        next_point = polygon[(index + 1) % len(polygon)]
        intersection = segment_intersection_point(p1, p2, current, next_point)
        if intersection is not None:
            points.append(intersection)

    return _dedupe_points(points)


def point_in_polygon(point: Point, polygon: list[Point]) -> bool:
    if len(polygon) < 3:
        return False

    inside = False
    previous = polygon[-1]
    for current in polygon:
        if _on_segment(previous, point, current):
            return True

        intersects_ray = (
            (current["y"] > point["y"]) != (previous["y"] > point["y"])
            and point["x"]
            < (previous["x"] - current["x"])
            * (point["y"] - current["y"])
            / ((previous["y"] - current["y"]) or EPSILON)
            + current["x"]
        )
        if intersects_ray:
            inside = not inside
        previous = current

    return inside


def segment_intersects_polygon(p1: Point, p2: Point, polygon: list[Point]) -> bool:
    if len(polygon) < 3:
        return False
    if point_in_polygon(p1, polygon) or point_in_polygon(p2, polygon):
        return True

    for index, current in enumerate(polygon):
        next_point = polygon[(index + 1) % len(polygon)]
        if segments_intersect(p1, p2, current, next_point):
            return True

    return False


def route_edge_intersects_camera_zone(edge, from_node, to_node, polygon: list[Point]) -> bool:
    del edge
    return segment_intersects_polygon(
        {"x": float(from_node.x), "y": float(from_node.y)},
        {"x": float(to_node.x), "y": float(to_node.y)},
        polygon,
    )


def polygon_centroid(points: list[Point]) -> Point:
    if not points:
        return {"x": 0.0, "y": 0.0}

    signed_area = 0.0
    centroid_x = 0.0
    centroid_y = 0.0

    for index, current in enumerate(points):
        next_point = points[(index + 1) % len(points)]
        cross = current["x"] * next_point["y"] - next_point["x"] * current["y"]
        signed_area += cross
        centroid_x += (current["x"] + next_point["x"]) * cross
        centroid_y += (current["y"] + next_point["y"]) * cross

    signed_area *= 0.5
    if abs(signed_area) <= EPSILON:
        return {
            "x": sum(point["x"] for point in points) / len(points),
            "y": sum(point["y"] for point in points) / len(points),
        }

    return {
        "x": centroid_x / (6.0 * signed_area),
        "y": centroid_y / (6.0 * signed_area),
    }
