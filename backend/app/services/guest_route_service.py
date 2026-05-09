from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from app.core.config import settings
from app.models.camera_visibility_zones import CameraVisibilityZone
from app.models.cameras import Camera
from app.models.guests import Guest
from app.models.logs import AccessLog, TrackingLog
from app.models.route_edges import RouteEdge
from app.models.route_nodes import RouteNode
from app.services.geometry_service import (
    distance as geometry_distance,
    point_on_segment_at,
    polygon_centroid,
    project_point_to_segment,
    route_edge_intersects_camera_zone,
    segment_polygon_intersection_points,
    segment_position,
)
from app.services.route_graph_service import RouteGraphError, find_shortest_path

ANCHOR_EPSILON = 1e-6


def _zone_points(zone: CameraVisibilityZone) -> list[dict[str, float]]:
    return [{"x": float(point["x"]), "y": float(point["y"])} for point in zone.points_json]


def _edge_payload(edge: RouteEdge) -> dict[str, Any]:
    return {
        "id": edge.id,
        "floor_id": edge.floor_id,
        "from_node_id": edge.from_node_id,
        "to_node_id": edge.to_node_id,
        "weight": edge.weight,
        "is_bidirectional": edge.is_bidirectional,
    }


def _node_payload(node: RouteNode) -> dict[str, Any]:
    return {"id": node.id, "x": node.x, "y": node.y}


def _node_point(node: RouteNode) -> dict[str, float]:
    return {"x": float(node.x), "y": float(node.y)}


def _edge_short_payload(edge: RouteEdge) -> dict[str, Any]:
    return {
        "id": edge.id,
        "from_node_id": edge.from_node_id,
        "to_node_id": edge.to_node_id,
        "weight": edge.weight,
    }


def _anchor_payload(
    edge: RouteEdge,
    from_node: RouteNode,
    to_node: RouteNode,
    polygon: list[dict[str, float]],
) -> dict[str, Any] | None:
    p1 = _node_point(from_node)
    p2 = _node_point(to_node)
    intersection_points = segment_polygon_intersection_points(p1, p2, polygon)
    if not intersection_points:
        if not route_edge_intersects_camera_zone(edge, from_node, to_node, polygon):
            return None
        # Fallback for degenerate geometry: snap the camera-zone center to the graph edge.
        anchor_point = project_point_to_segment(polygon_centroid(polygon), p1, p2)
    else:
        positions = [segment_position(point, p1, p2) for point in intersection_points]
        anchor_position = (min(positions) + max(positions)) / 2.0
        anchor_point = point_on_segment_at(p1, p2, anchor_position)

    position = segment_position(anchor_point, p1, p2)
    edge_weight = float(edge.weight or geometry_distance(p1, p2))
    return {
        "edge_id": edge.id,
        "from_node_id": edge.from_node_id,
        "to_node_id": edge.to_node_id,
        "x": anchor_point["x"],
        "y": anchor_point["y"],
        "position": position,
        "distance_from_from": edge_weight * position,
        "distance_to_to": edge_weight * (1.0 - position),
        "is_bidirectional": edge.is_bidirectional,
    }


def _anchor_node_payload(anchor: dict[str, Any], event_index: int, role: str) -> dict[str, Any]:
    return {
        "id": f"event-{event_index}-{role}-anchor-{anchor['edge_id']}",
        "x": float(anchor["x"]),
        "y": float(anchor["y"]),
        "is_anchor": True,
        "edge_id": anchor["edge_id"],
    }


def get_camera_route_candidates(
    session: Session,
    floor_id: int,
    camera_id: int,
) -> dict[str, Any]:
    zone = session.exec(
        select(CameraVisibilityZone).where(
            CameraVisibilityZone.floor_id == floor_id,
            CameraVisibilityZone.camera_id == camera_id,
        )
    ).first()

    if not zone:
        return {
            "camera_id": camera_id,
            "zone": None,
            "candidate_edges": [],
            "candidate_node_ids": [],
            "candidate_anchors": [],
            "primary_anchor": None,
        }

    polygon = _zone_points(zone)
    nodes = session.exec(select(RouteNode).where(RouteNode.floor_id == floor_id)).all()
    nodes_by_id = {node.id: node for node in nodes if node.id is not None}
    edges = session.exec(select(RouteEdge).where(RouteEdge.floor_id == floor_id)).all()

    candidate_edges: list[RouteEdge] = []
    candidate_node_ids: set[int] = set()
    candidate_anchors: list[dict[str, Any]] = []

    for edge in edges:
        from_node = nodes_by_id.get(edge.from_node_id)
        to_node = nodes_by_id.get(edge.to_node_id)
        if not from_node or not to_node:
            continue

        if route_edge_intersects_camera_zone(edge, from_node, to_node, polygon):
            candidate_edges.append(edge)
            candidate_node_ids.add(edge.from_node_id)
            candidate_node_ids.add(edge.to_node_id)
            anchor = _anchor_payload(edge, from_node, to_node, polygon)
            if anchor is not None:
                candidate_anchors.append(anchor)

    zone_center = polygon_centroid(polygon)
    primary_anchor = None
    if candidate_anchors:
        primary_anchor = min(
            candidate_anchors,
            key=lambda anchor: geometry_distance(
                {"x": float(anchor["x"]), "y": float(anchor["y"])},
                zone_center,
            ),
        )

    return {
        "camera_id": camera_id,
        "zone": polygon,
        "candidate_edges": [_edge_payload(edge) for edge in candidate_edges],
        "candidate_node_ids": sorted(candidate_node_ids),
        "candidate_anchors": candidate_anchors,
        "primary_anchor": primary_anchor,
    }


def get_floor_camera_route_candidates(session: Session, floor_id: int) -> dict[str, Any]:
    cameras = session.exec(
        select(Camera)
        .where(Camera.floor_id == floor_id)
        .where(Camera.is_active.is_(True))
        .order_by(Camera.name.asc(), Camera.id.asc())
    ).all()

    candidates = []
    warnings = []
    for camera in cameras:
        item = get_camera_route_candidates(session, floor_id, camera.id)
        item["camera_name"] = camera.name
        candidates.append(item)

        if not item["zone"]:
            warnings.append(f"Для камеры {camera.name} не задана зона видимости")
        elif not item["candidate_node_ids"]:
            warnings.append(f"Зона камеры {camera.name} не пересекается с графом маршрутов")

    return {
        "floor_id": floor_id,
        "cameras": candidates,
        "warnings": warnings,
    }


def _fetch_tracking_events(
    session: Session,
    guest_id: int,
    floor_id: int,
    time_from: datetime | None,
    time_to: datetime | None,
) -> list[dict[str, Any]]:
    statement = (
        select(TrackingLog, Camera)
        .join(Camera, TrackingLog.camera_id == Camera.id)
        .where(
            TrackingLog.guest_id == guest_id,
            Camera.floor_id == floor_id,
            Camera.is_active.is_(True),
        )
    )
    if time_from is not None:
        statement = statement.where(TrackingLog.timestamp >= time_from)
    if time_to is not None:
        statement = statement.where(TrackingLog.timestamp <= time_to)

    rows = session.exec(statement.order_by(TrackingLog.timestamp.asc(), TrackingLog.id.asc())).all()
    return [
        {
            "tracking_log_id": log.id,
            "access_log_id": None,
            "source": "tracking_log",
            "camera_id": log.camera_id,
            "camera_name": camera.name if camera else None,
            "timestamp": log.timestamp,
            "confidence": log.confidence,
        }
        for log, camera in rows
        if log.camera_id is not None
    ]


def _fetch_access_events(
    session: Session,
    guest_id: int,
    floor_id: int,
    time_from: datetime | None,
    time_to: datetime | None,
) -> list[dict[str, Any]]:
    statement = (
        select(AccessLog, Camera)
        .join(Camera, AccessLog.camera_id == Camera.id)
        .where(
            AccessLog.guest_id == guest_id,
            Camera.floor_id == floor_id,
            Camera.is_active.is_(True),
        )
    )
    if time_from is not None:
        statement = statement.where(AccessLog.timestamp >= time_from)
    if time_to is not None:
        statement = statement.where(AccessLog.timestamp <= time_to)

    rows = session.exec(statement.order_by(AccessLog.timestamp.asc(), AccessLog.id.asc())).all()
    return [
        {
            "tracking_log_id": None,
            "access_log_id": log.id,
            "source": "access_log",
            "camera_id": log.camera_id,
            "camera_name": camera.name if camera else None,
            "timestamp": log.timestamp,
            "confidence": log.confidence,
        }
        for log, camera in rows
        if log.camera_id is not None
    ]


def _collapse_consecutive_camera_duplicates(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    collapsed = []
    previous_camera_id = None
    for event in events:
        if event["camera_id"] == previous_camera_id:
            continue
        collapsed.append(event)
        previous_camera_id = event["camera_id"]
    return collapsed


def _filter_low_confidence_events(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    threshold = float(settings.guest_route_min_event_confidence)
    if threshold <= 0:
        return events, []

    filtered_events: list[dict[str, Any]] = []
    dropped_count = 0
    for event in events:
        confidence = event.get("confidence")
        if (
            event.get("source") == "tracking_log"
            and confidence is not None
            and float(confidence) < threshold
        ):
            dropped_count += 1
            continue
        filtered_events.append(event)

    if dropped_count <= 0:
        return filtered_events, []

    return filtered_events, [
        f"Отброшено {dropped_count} событий ниже порога достоверности {threshold:.2f}"
    ]


def _event_has_route_candidates(event: dict[str, Any]) -> bool:
    return bool(event.get("candidate_anchors") or event.get("candidate_node_ids"))


def _route_anchors_for_candidate(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    primary_anchor = candidate.get("primary_anchor")
    if primary_anchor:
        return [primary_anchor]
    return candidate.get("candidate_anchors") or []


def _keep_latest_event_per_camera(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    if not settings.guest_route_keep_latest_event_per_camera or len(events) <= 1:
        return events, []

    latest_by_camera_id: dict[int, dict[str, Any]] = {}
    for event in events:
        latest_by_camera_id[int(event["camera_id"])] = event

    filtered_events = sorted(
        latest_by_camera_id.values(),
        key=lambda event: (event["timestamp"], event.get("tracking_log_id") or event.get("access_log_id") or 0),
    )
    dropped_count = len(events) - len(filtered_events)
    if dropped_count <= 0:
        return filtered_events, []

    return filtered_events, [
        f"Отброшено {dropped_count} повторных событий камер; оставлено последнее событие по каждой камере"
    ]


def _find_best_candidate_path(
    session: Session,
    floor_id: int,
    start_node_ids: list[int],
    end_node_ids: list[int],
):
    best_path = None
    best_distance = float("inf")
    best_zero_path = None

    for start_node_id in start_node_ids:
        for end_node_id in end_node_ids:
            try:
                path = find_shortest_path(session, floor_id, start_node_id, end_node_id)
            except RouteGraphError:
                continue

            if path.distance <= 0:
                if best_zero_path is None:
                    best_zero_path = path
                continue

            if path.distance < best_distance:
                best_path = path
                best_distance = path.distance

    return best_path or best_zero_path


def _anchor_exit_options(anchor: dict[str, Any]) -> list[tuple[int, float]]:
    if anchor.get("is_bidirectional"):
        return [
            (int(anchor["from_node_id"]), float(anchor["distance_from_from"])),
            (int(anchor["to_node_id"]), float(anchor["distance_to_to"])),
        ]
    return [(int(anchor["to_node_id"]), float(anchor["distance_to_to"]))]


def _anchor_entry_options(anchor: dict[str, Any]) -> list[tuple[int, float]]:
    if anchor.get("is_bidirectional"):
        return [
            (int(anchor["from_node_id"]), float(anchor["distance_from_from"])),
            (int(anchor["to_node_id"]), float(anchor["distance_to_to"])),
        ]
    return [(int(anchor["from_node_id"]), float(anchor["distance_from_from"]))]


def _append_edge_payload(edge_payloads: list[dict[str, Any]], edge: RouteEdge | None) -> None:
    if not edge or edge.id is None:
        return
    if edge_payloads and edge_payloads[-1].get("id") == edge.id:
        return
    edge_payloads.append(_edge_short_payload(edge))


def _build_anchor_path(
    session: Session,
    floor_id: int,
    start_anchor: dict[str, Any],
    end_anchor: dict[str, Any],
    *,
    start_event_index: int,
    end_event_index: int,
) -> dict[str, Any] | None:
    start_edge = session.get(RouteEdge, start_anchor["edge_id"])
    end_edge = session.get(RouteEdge, end_anchor["edge_id"])
    if not start_edge or not end_edge:
        return None

    start_anchor_node = _anchor_node_payload(start_anchor, start_event_index, "start")
    end_anchor_node = _anchor_node_payload(end_anchor, end_event_index, "end")
    best: dict[str, Any] | None = None

    if start_anchor["edge_id"] == end_anchor["edge_id"]:
        start_position = float(start_anchor["position"])
        end_position = float(end_anchor["position"])
        can_walk_directly = start_edge.is_bidirectional or end_position >= start_position
        if can_walk_directly:
            direct_distance = abs(end_position - start_position) * float(start_edge.weight or 0.0)
            best = {
                "nodes": [start_anchor_node, end_anchor_node],
                "edges": [_edge_short_payload(start_edge)] if direct_distance > ANCHOR_EPSILON else [],
                "distance": direct_distance,
                "start_anchor": start_anchor,
                "end_anchor": end_anchor,
            }

    for exit_node_id, start_cost in _anchor_exit_options(start_anchor):
        for entry_node_id, end_cost in _anchor_entry_options(end_anchor):
            try:
                graph_path = find_shortest_path(session, floor_id, exit_node_id, entry_node_id)
            except RouteGraphError:
                continue

            segment_distance = start_cost + graph_path.distance + end_cost
            if best is not None and segment_distance >= best["distance"]:
                continue

            edge_payloads: list[dict[str, Any]] = []
            if start_cost > ANCHOR_EPSILON:
                _append_edge_payload(edge_payloads, start_edge)
            for edge in graph_path.edges:
                _append_edge_payload(edge_payloads, edge)
            if end_cost > ANCHOR_EPSILON:
                _append_edge_payload(edge_payloads, end_edge)

            best = {
                "nodes": [
                    start_anchor_node,
                    *[_node_payload(node) for node in graph_path.nodes],
                    end_anchor_node,
                ],
                "edges": edge_payloads,
                "distance": segment_distance,
                "start_anchor": start_anchor,
                "end_anchor": end_anchor,
            }

    return best


def _find_best_anchor_path(
    session: Session,
    floor_id: int,
    start_anchors: list[dict[str, Any]],
    end_anchors: list[dict[str, Any]],
    *,
    start_event_index: int,
    end_event_index: int,
) -> dict[str, Any] | None:
    best_path = None
    for start_anchor in start_anchors:
        for end_anchor in end_anchors:
            path = _build_anchor_path(
                session,
                floor_id,
                start_anchor,
                end_anchor,
                start_event_index=start_event_index,
                end_event_index=end_event_index,
            )
            if path is None:
                continue
            if best_path is None or path["distance"] < best_path["distance"]:
                best_path = path
    return best_path


def _transition_distance(
    session: Session,
    floor_id: int,
    from_event: dict[str, Any],
    to_event: dict[str, Any],
) -> float | None:
    dt = (to_event["timestamp"] - from_event["timestamp"]).total_seconds()
    if dt <= 0 or dt > settings.guest_route_max_event_gap_sec:
        return None

    anchor_path = _find_best_anchor_path(
        session,
        floor_id,
        from_event.get("candidate_anchors") or [],
        to_event.get("candidate_anchors") or [],
        start_event_index=0,
        end_event_index=1,
    )
    if anchor_path is not None:
        distance = anchor_path["distance"]
    else:
        path = _find_best_candidate_path(
            session,
            floor_id,
            from_event.get("candidate_node_ids") or [],
            to_event.get("candidate_node_ids") or [],
        )
        if path is None:
            return None
        distance = path.distance

    speed = distance / max(dt, 1.0)
    if speed > settings.guest_route_max_pixels_per_second:
        return None
    return float(distance)


def _transition_is_plausible(
    session: Session,
    floor_id: int,
    from_event: dict[str, Any],
    to_event: dict[str, Any],
) -> bool:
    return _transition_distance(session, floor_id, from_event, to_event) is not None


def _filter_plausible_event_chain(
    session: Session,
    floor_id: int,
    events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    if len(events) <= 2:
        return events, []

    chain_lengths = [1 for _ in events]
    chain_distances = [0.0 for _ in events]
    chain_confidences = [float(event.get("confidence") or 0.0) for event in events]
    previous_indexes: list[int | None] = [None for _ in events]

    for current_index in range(len(events)):
        for previous_index in range(current_index):
            transition_distance = _transition_distance(
                session,
                floor_id,
                events[previous_index],
                events[current_index],
            )
            if transition_distance is None:
                continue

            candidate_length = chain_lengths[previous_index] + 1
            candidate_distance = chain_distances[previous_index] + transition_distance
            candidate_confidence = chain_confidences[previous_index] + float(
                events[current_index].get("confidence") or 0.0
            )

            is_better = candidate_length > chain_lengths[current_index]
            if candidate_length == chain_lengths[current_index]:
                is_better = (
                    candidate_distance < chain_distances[current_index]
                    or (
                        abs(candidate_distance - chain_distances[current_index]) <= ANCHOR_EPSILON
                        and candidate_confidence > chain_confidences[current_index]
                    )
                )

            if not is_better:
                continue

            chain_lengths[current_index] = candidate_length
            chain_distances[current_index] = candidate_distance
            chain_confidences[current_index] = candidate_confidence
            previous_indexes[current_index] = previous_index

    best_index = max(
        range(len(events)),
        key=lambda index: (
            chain_lengths[index],
            -chain_distances[index],
            chain_confidences[index],
        ),
    )
    if chain_lengths[best_index] < 2:
        return events, []

    selected_indexes = []
    current_index: int | None = best_index
    while current_index is not None:
        selected_indexes.append(current_index)
        current_index = previous_indexes[current_index]
    selected_indexes.reverse()

    selected_set = set(selected_indexes)
    filtered_events = [event for index, event in enumerate(events) if index in selected_set]
    dropped_count = len(events) - len(filtered_events)
    warnings = []
    if dropped_count > 0:
        warnings.append(
            f"Отброшено {dropped_count} низкодостоверных/неправдоподобных событий маршрута"
        )

    return filtered_events, warnings


def _append_route_segment(
    route_nodes: list[dict[str, Any]],
    route_edges: list[dict[str, Any]],
    segment_nodes: list[dict[str, Any]],
    segment_edges: list[dict[str, Any]],
) -> None:
    for node in segment_nodes:
        if (
            route_nodes
            and abs(float(route_nodes[-1]["x"]) - float(node["x"])) <= ANCHOR_EPSILON
            and abs(float(route_nodes[-1]["y"]) - float(node["y"])) <= ANCHOR_EPSILON
        ):
            continue
        route_nodes.append(node)

    for edge in segment_edges:
        if route_edges and route_edges[-1].get("id") == edge.get("id"):
            continue
        route_edges.append(edge)


def build_guest_probable_route(
    session: Session,
    guest_id: int,
    floor_id: int,
    time_from: datetime | None = None,
    time_to: datetime | None = None,
) -> dict[str, Any]:
    guest = session.get(Guest, guest_id)
    if not guest:
        raise ValueError("Гость не найден")

    raw_events = _fetch_tracking_events(session, guest_id, floor_id, time_from, time_to)
    if not raw_events:
        raw_events = _fetch_access_events(session, guest_id, floor_id, time_from, time_to)

    confidence_filtered_events, confidence_warnings = _filter_low_confidence_events(raw_events)
    events = _collapse_consecutive_camera_duplicates(confidence_filtered_events)
    warnings: list[str] = list(confidence_warnings)
    camera_zones_by_id: dict[int, dict[str, Any]] = {}
    candidates_by_camera_id: dict[int, dict[str, Any]] = {}

    if not events:
        if raw_events:
            warnings.append("После фильтрации достоверных событий маршрута не осталось")
        else:
            warnings.append("За выбранный период событий не найдено")

    for event in events:
        candidate = get_camera_route_candidates(session, floor_id, event["camera_id"])
        candidates_by_camera_id[event["camera_id"]] = candidate
        route_anchors = _route_anchors_for_candidate(candidate)
        event["candidate_node_ids"] = candidate["candidate_node_ids"]
        event["candidate_anchors"] = route_anchors
        event["route_anchor"] = route_anchors[0] if route_anchors else None

        if candidate["zone"]:
            camera_zones_by_id[event["camera_id"]] = {
                "camera_id": event["camera_id"],
                "camera_name": event.get("camera_name"),
                "points": candidate["zone"],
            }
        else:
            warnings.append(
                f"Для камеры {event.get('camera_name') or event['camera_id']} не задана зона видимости"
            )

        if candidate["zone"] and not candidate["candidate_node_ids"]:
            warnings.append(
                f"Зона камеры {event.get('camera_name') or event['camera_id']} не пересекается с графом маршрутов"
            )

    invalid_events = [event for event in events if not _event_has_route_candidates(event)]
    if invalid_events:
        invalid_camera_names = [
            str(event.get("camera_name") or event["camera_id"]) for event in invalid_events
        ]
        warnings.append(
            "Из маршрута исключены события камер без пересечения зоны с графом: "
            + ", ".join(invalid_camera_names)
        )
        events = [event for event in events if _event_has_route_candidates(event)]
        camera_zones_by_id = {
            camera_id: zone
            for camera_id, zone in camera_zones_by_id.items()
            if any(event["camera_id"] == camera_id for event in events)
        }

    events, repeated_event_warnings = _keep_latest_event_per_camera(events)
    if repeated_event_warnings:
        warnings.extend(repeated_event_warnings)
        camera_zones_by_id = {
            camera_id: zone
            for camera_id, zone in camera_zones_by_id.items()
            if any(event["camera_id"] == camera_id for event in events)
        }

    unique_camera_ids = []
    for event in events:
        if event["camera_id"] not in unique_camera_ids:
            unique_camera_ids.append(event["camera_id"])

    filtered_events, chain_warnings = _filter_plausible_event_chain(session, floor_id, events)
    if len(filtered_events) >= 2 and len(filtered_events) < len(events):
        events = filtered_events
        warnings.extend(chain_warnings)
        camera_zones_by_id = {
            camera_id: zone
            for camera_id, zone in camera_zones_by_id.items()
            if any(event["camera_id"] == camera_id for event in events)
        }
        unique_camera_ids = []
        for event in events:
            if event["camera_id"] not in unique_camera_ids:
                unique_camera_ids.append(event["camera_id"])

    if len(unique_camera_ids) < 2:
        if events:
            warnings.append("Для построения маршрута нужно минимум две разные камеры")
        return {
            "guest_id": guest_id,
            "floor_id": floor_id,
            "events": events,
            "route_nodes": [],
            "route_edges": [],
            "camera_zones": list(camera_zones_by_id.values()),
            "distance": 0.0,
            "warnings": warnings,
        }

    route_nodes: list[dict[str, Any]] = []
    route_edges: list[dict[str, Any]] = []
    total_distance = 0.0

    for index in range(len(events) - 1):
        current_event = events[index]
        next_event = events[index + 1]
        current_candidates = candidates_by_camera_id.get(current_event["camera_id"]) or {}
        next_candidates = candidates_by_camera_id.get(next_event["camera_id"]) or {}
        current_anchors = current_event.get("candidate_anchors") or []
        next_anchors = next_event.get("candidate_anchors") or []
        current_node_ids = current_candidates.get("candidate_node_ids") or []
        next_node_ids = next_candidates.get("candidate_node_ids") or []

        if current_anchors and next_anchors:
            best_anchor_path = _find_best_anchor_path(
                session,
                floor_id,
                current_anchors,
                next_anchors,
                start_event_index=index,
                end_event_index=index + 1,
            )
            if best_anchor_path is not None:
                current_event["route_anchor"] = best_anchor_path["start_anchor"]
                next_event["route_anchor"] = best_anchor_path["end_anchor"]
                _append_route_segment(
                    route_nodes,
                    route_edges,
                    best_anchor_path["nodes"],
                    best_anchor_path["edges"],
                )
                total_distance += best_anchor_path["distance"]
                continue

        if not current_node_ids or not next_node_ids:
            warnings.append(
                "Нельзя построить участок маршрута между "
                f"{current_event.get('camera_name') or current_event['camera_id']} и "
                f"{next_event.get('camera_name') or next_event['camera_id']}: нет candidate_node_ids"
            )
            continue

        best_path = _find_best_candidate_path(
            session,
            floor_id,
            current_node_ids,
            next_node_ids,
        )
        if best_path is None:
            warnings.append(
                "Маршрут между зонами камер "
                f"{current_event.get('camera_name') or current_event['camera_id']} и "
                f"{next_event.get('camera_name') or next_event['camera_id']} не найден"
            )
            continue

        _append_route_segment(
            route_nodes,
            route_edges,
            [_node_payload(node) for node in best_path.nodes],
            [_edge_short_payload(edge) for edge in best_path.edges],
        )
        total_distance += best_path.distance

    return {
        "guest_id": guest_id,
        "floor_id": floor_id,
        "events": events,
        "route_nodes": route_nodes,
        "route_edges": route_edges,
        "camera_zones": list(camera_zones_by_id.values()),
        "distance": total_distance,
        "warnings": warnings,
    }
