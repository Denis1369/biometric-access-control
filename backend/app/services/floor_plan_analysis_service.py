from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def _point(x: float, y: float, width: int, height: int) -> dict[str, float]:
    return {
        "x": max(0.0, min(1.0, float(x) / max(width, 1))),
        "y": max(0.0, min(1.0, float(y) / max(height, 1))),
    }


def _contour_to_polygon(
    contour: np.ndarray,
    width: int,
    height: int,
    *,
    max_points: int = 16,
) -> list[dict[str, float]]:
    perimeter = cv2.arcLength(contour, True)
    epsilon = max(1.5, 0.01 * perimeter)
    approx = cv2.approxPolyDP(contour, epsilon, True)
    points = approx.reshape(-1, 2)
    if len(points) > max_points:
        step = max(1, len(points) // max_points)
        points = points[::step][:max_points]
    return [_point(float(x), float(y), width, height) for x, y in points]


def _line_length(line: dict[str, float]) -> float:
    return float(np.hypot(line["x2"] - line["x1"], line["y2"] - line["y1"]))


def analyze_floor_plan_image(image_bytes: bytes) -> dict[str, Any]:
    """Heuristic raster floor-plan analysis.

    This is intentionally conservative: it gives the operator useful hints
    over the plan, but manual camera zone markup remains the source of truth.
    """

    array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Не удалось прочитать изображение плана")

    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    dark_mask = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        7,
    )
    kernel = np.ones((3, 3), np.uint8)
    dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_CLOSE, kernel, iterations=1)

    edges = cv2.Canny(dark_mask, 40, 120)
    raw_lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=45,
        minLineLength=max(12, min(width, height) // 24),
        maxLineGap=max(4, min(width, height) // 80),
    )

    wall_segments: list[dict[str, float]] = []
    door_candidates: list[dict[str, float]] = []
    if raw_lines is not None:
        for raw_line in raw_lines[:350]:
            x1, y1, x2, y2 = raw_line[0]
            line = {
                "x1": _point(x1, y1, width, height)["x"],
                "y1": _point(x1, y1, width, height)["y"],
                "x2": _point(x2, y2, width, height)["x"],
                "y2": _point(x2, y2, width, height)["y"],
            }
            length = _line_length(line)
            if length >= 0.055:
                wall_segments.append(line)
            elif 0.018 <= length <= 0.08:
                door_candidates.append({**line, "confidence": 0.25})

    wall_segments = sorted(wall_segments, key=_line_length, reverse=True)[:140]
    door_candidates = sorted(door_candidates, key=_line_length, reverse=True)[:40]

    # Bright connected areas are a useful approximation of walkable/room space
    # on simple architectural plans.
    _, bright_mask = cv2.threshold(gray, 205, 255, cv2.THRESH_BINARY)
    bright_mask = cv2.morphologyEx(bright_mask, cv2.MORPH_OPEN, kernel, iterations=1)
    bright_mask = cv2.morphologyEx(bright_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(bright_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_area = max(120, int(width * height * 0.003))
    rooms: list[dict[str, Any]] = []
    corridors: list[dict[str, Any]] = []
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:80]:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        if w >= width * 0.96 and h >= height * 0.96:
            continue
        aspect = max(w / max(h, 1), h / max(w, 1))
        item = {
            "polygon": _contour_to_polygon(contour, width, height),
            "area_ratio": float(area / max(width * height, 1)),
            "confidence": 0.45 if aspect > 2.2 else 0.35,
        }
        if aspect > 2.2:
            corridors.append(item)
        else:
            rooms.append(item)

    if not corridors and wall_segments:
        xs = [value for line in wall_segments for value in (line["x1"], line["x2"])]
        ys = [value for line in wall_segments for value in (line["y1"], line["y2"])]
        min_x = max(0.0, min(xs) - 0.04)
        max_x = min(1.0, max(xs) + 0.04)
        min_y = max(0.0, min(ys) - 0.04)
        max_y = min(1.0, max(ys) + 0.04)
        if max_x - min_x > 0.08 and max_y - min_y > 0.08:
            corridors.append(
                {
                    "polygon": [
                        {"x": min_x, "y": min_y},
                        {"x": max_x, "y": min_y},
                        {"x": max_x, "y": max_y},
                        {"x": min_x, "y": max_y},
                    ],
                    "area_ratio": float((max_x - min_x) * (max_y - min_y)),
                    "confidence": 0.2,
                }
            )

    return {
        "version": 1,
        "image_width": width,
        "image_height": height,
        "walls": wall_segments,
        "corridors": corridors[:30],
        "rooms": rooms[:40],
        "doors": door_candidates,
        "note": (
            "Эвристический анализ плана: используйте как подсказку, "
            "а зоны видимости камер размечайте вручную."
        ),
    }
