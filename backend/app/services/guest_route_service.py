from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from app.models.camera_visibility_zones import CameraVisibilityZone
from app.models.cameras import Camera
from app.models.guests import Guest
from app.models.logs import AccessLog, TrackingLog
from app.models.route_edges import RouteEdge
from app.models.route_nodes import RouteNode
from app.services.geometry_service import route_edge_intersects_camera_zone
from app.services.route_graph_service import RouteGraphError, find_shortest_path


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
        }

    polygon = _zone_points(zone)
    nodes = session.exec(select(RouteNode).where(RouteNode.floor_id == floor_id)).all()
    nodes_by_id = {node.id: node for node in nodes if node.id is not None}
    edges = session.exec(select(RouteEdge).where(RouteEdge.floor_id == floor_id)).all()

    candidate_edges: list[RouteEdge] = []
    candidate_node_ids: set[int] = set()

    for edge in edges:
        from_node = nodes_by_id.get(edge.from_node_id)
        to_node = nodes_by_id.get(edge.to_node_id)
        if not from_node or not to_node:
            continue

        if route_edge_intersects_camera_zone(edge, from_node, to_node, polygon):
            candidate_edges.append(edge)
            candidate_node_ids.add(edge.from_node_id)
            candidate_node_ids.add(edge.to_node_id)

    return {
        "camera_id": camera_id,
        "zone": polygon,
        "candidate_edges": [_edge_payload(edge) for edge in candidate_edges],
        "candidate_node_ids": sorted(candidate_node_ids),
    }


def get_floor_camera_route_candidates(session: Session, floor_id: int) -> dict[str, Any]:
    cameras = session.exec(
        select(Camera)
        .where(Camera.floor_id == floor_id)
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
        .where(TrackingLog.guest_id == guest_id, Camera.floor_id == floor_id)
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
        .where(AccessLog.guest_id == guest_id, Camera.floor_id == floor_id)
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


def _find_best_candidate_path(
    session: Session,
    floor_id: int,
    start_node_ids: list[int],
    end_node_ids: list[int],
):
    best_path = None
    best_distance = float("inf")

    for start_node_id in start_node_ids:
        for end_node_id in end_node_ids:
            try:
                path = find_shortest_path(session, floor_id, start_node_id, end_node_id)
            except RouteGraphError:
                continue

            if path.distance < best_distance:
                best_path = path
                best_distance = path.distance

    return best_path


def _append_path(
    route_nodes: list[RouteNode],
    route_edges: list[RouteEdge],
    path_nodes: list[RouteNode],
    path_edges: list[RouteEdge],
) -> None:
    for node in path_nodes:
        if route_nodes and route_nodes[-1].id == node.id:
            continue
        route_nodes.append(node)

    for edge in path_edges:
        if route_edges and route_edges[-1].id == edge.id:
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

    events = _collapse_consecutive_camera_duplicates(raw_events)
    warnings: list[str] = []
    camera_zones_by_id: dict[int, dict[str, Any]] = {}
    candidates_by_camera_id: dict[int, dict[str, Any]] = {}

    if not events:
        warnings.append("За выбранный период событий не найдено")

    for event in events:
        candidate = get_camera_route_candidates(session, floor_id, event["camera_id"])
        candidates_by_camera_id[event["camera_id"]] = candidate
        event["candidate_node_ids"] = candidate["candidate_node_ids"]

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

    route_nodes: list[RouteNode] = []
    route_edges: list[RouteEdge] = []
    total_distance = 0.0

    for index in range(len(events) - 1):
        current_event = events[index]
        next_event = events[index + 1]
        current_candidates = candidates_by_camera_id.get(current_event["camera_id"]) or {}
        next_candidates = candidates_by_camera_id.get(next_event["camera_id"]) or {}
        current_node_ids = current_candidates.get("candidate_node_ids") or []
        next_node_ids = next_candidates.get("candidate_node_ids") or []

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

        _append_path(route_nodes, route_edges, best_path.nodes, best_path.edges)
        total_distance += best_path.distance

    return {
        "guest_id": guest_id,
        "floor_id": floor_id,
        "events": events,
        "route_nodes": [_node_payload(node) for node in route_nodes],
        "route_edges": [
            {
                "id": edge.id,
                "from_node_id": edge.from_node_id,
                "to_node_id": edge.to_node_id,
                "weight": edge.weight,
            }
            for edge in route_edges
        ],
        "camera_zones": list(camera_zones_by_id.values()),
        "distance": total_distance,
        "warnings": warnings,
    }
