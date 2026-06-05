"""Сервис ручного графа маршрутов.

Оператор рисует технические точки и линии маршрута поверх плана этажа. Модуль
проверяет изменения графа и запускает алгоритм Дейкстры для поиска кратчайшего
пути между двумя точками. Зоны камер и маршруты гостей переиспользуют этот граф,
а не считают камеры самостоятельными точками маршрута.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, or_
from sqlmodel import Session, select

from app.models.floors import Floor
from app.models.route_edges import RouteEdge
from app.models.route_nodes import RouteNode


class RouteGraphError(ValueError):
    """Доменная ошибка графа, которую API преобразует в HTTP-ответ.

    Сервис не зависит от FastAPI и не выбрасывает HTTPException напрямую. Так
    его можно использовать из разных мест backend-а, а router сам решает, какой
    статус ответа вернуть пользователю.
    """


class RouteNotFoundError(RouteGraphError):
    """Ошибка ситуации, когда граф корректен, но путь между точками не найден."""


@dataclass(frozen=True)
class RoutePath:
    """Результат кратчайшего пути, найденного алгоритмом Дейкстры.

    Атрибуты:
        nodes: упорядоченные точки графа от начала до конца.
        edges: упорядоченные линии графа между точками.
        distance: суммарный вес пути в пикселях плана этажа.
    """

    nodes: list[RouteNode]
    edges: list[RouteEdge]
    distance: float


def ensure_floor_exists(session: Session, floor_id: int) -> Floor:
    """Загрузить этаж или выбросить доменную ошибку для API-обработчиков."""
    floor = session.get(Floor, floor_id)
    if not floor:
        raise RouteGraphError("Этаж не найден")
    return floor


def get_floor_graph(session: Session, floor_id: int) -> tuple[list[RouteNode], list[RouteEdge]]:
    """Вернуть все точки и линии маршрута этажа в стабильном порядке."""
    ensure_floor_exists(session, floor_id)
    nodes = session.exec(
        select(RouteNode)
        .where(RouteNode.floor_id == floor_id)
        .order_by(RouteNode.id.asc())
    ).all()
    edges = session.exec(
        select(RouteEdge)
        .where(RouteEdge.floor_id == floor_id)
        .order_by(RouteEdge.id.asc())
    ).all()
    return list(nodes), list(edges)


def create_route_node(session: Session, floor_id: int, x: float, y: float) -> RouteNode:
    """Создать техническую точку маршрута на плане этажа.

    Параметры:
        session: сессия работы с базой данных.
        floor_id: этаж, на котором ставится точка.
        x: координата X в пикселях исходного изображения плана.
        y: координата Y в пикселях исходного изображения плана.
    """
    ensure_floor_exists(session, floor_id)
    node = RouteNode(floor_id=floor_id, x=x, y=y)
    session.add(node)
    session.commit()
    session.refresh(node)
    return node


def update_route_node(session: Session, node_id: int, x: float | None, y: float | None) -> RouteNode:
    """Передвинуть точку маршрута и пересчитать веса связанных линий."""
    node = session.get(RouteNode, node_id)
    if not node:
        raise RouteGraphError("Точка маршрута не найдена")

    if x is not None:
        node.x = x
    if y is not None:
        node.y = y
    node.updated_at = datetime.now()

    # При перемещении точки меняется геометрическая длина всех линий,
    # подключённых к этой точке, поэтому веса нужно пересчитать сразу.
    attached_edges = session.exec(
        select(RouteEdge).where(
            or_(
                RouteEdge.from_node_id == node.id,
                RouteEdge.to_node_id == node.id,
            )
        )
    ).all()
    for edge in attached_edges:
        from_node = session.get(RouteNode, edge.from_node_id)
        to_node = session.get(RouteNode, edge.to_node_id)
        if from_node and to_node:
            edge.weight = calculate_weight(from_node, to_node)
            edge.updated_at = datetime.now()
            session.add(edge)

    session.add(node)
    session.commit()
    session.refresh(node)
    return node


def delete_route_node(session: Session, node_id: int) -> None:
    """Удалить точку маршрута вместе со всеми связанными с ней линиями."""
    node = session.get(RouteNode, node_id)
    if not node:
        raise RouteGraphError("Точка маршрута не найдена")

    edges = session.exec(
        select(RouteEdge).where(
            or_(
                RouteEdge.from_node_id == node.id,
                RouteEdge.to_node_id == node.id,
            )
        )
    ).all()
    for edge in edges:
        session.delete(edge)
    session.delete(node)
    session.commit()


def calculate_weight(from_node: RouteNode, to_node: RouteNode) -> float:
    """Рассчитать евклидов вес линии между двумя точками плана."""
    return math.hypot(to_node.x - from_node.x, to_node.y - from_node.y)


def find_duplicate_edge(
    session: Session,
    floor_id: int,
    from_node_id: int,
    to_node_id: int,
) -> RouteEdge | None:
    """Найти существующую линию независимо от направления A-B или B-A."""
    return session.exec(
        select(RouteEdge).where(
            RouteEdge.floor_id == floor_id,
            or_(
                and_(
                    RouteEdge.from_node_id == from_node_id,
                    RouteEdge.to_node_id == to_node_id,
                ),
                and_(
                    RouteEdge.from_node_id == to_node_id,
                    RouteEdge.to_node_id == from_node_id,
                ),
            ),
        )
    ).first()


def create_route_edge(
    session: Session,
    floor_id: int,
    from_node_id: int,
    to_node_id: int,
    is_bidirectional: bool = True,
) -> RouteEdge:
    """Создать линию графа между двумя точками и запретить некорректные дубли."""
    ensure_floor_exists(session, floor_id)
    if from_node_id == to_node_id:
        raise RouteGraphError("Нельзя создать линию от точки к самой себе")

    from_node = session.get(RouteNode, from_node_id)
    to_node = session.get(RouteNode, to_node_id)
    if not from_node or not to_node:
        raise RouteGraphError("Одна или обе точки маршрута не найдены")
    if from_node.floor_id != floor_id or to_node.floor_id != floor_id:
        raise RouteGraphError("Обе точки должны принадлежать выбранному этажу")

    existing_edge = find_duplicate_edge(session, floor_id, from_node_id, to_node_id)
    if existing_edge:
        return existing_edge

    edge = RouteEdge(
        floor_id=floor_id,
        from_node_id=from_node_id,
        to_node_id=to_node_id,
        weight=calculate_weight(from_node, to_node),
        is_bidirectional=is_bidirectional,
    )
    session.add(edge)
    session.commit()
    session.refresh(edge)
    return edge


def delete_route_edge(session: Session, edge_id: int) -> None:
    """Удалить одну линию маршрута по id."""
    edge = session.get(RouteEdge, edge_id)
    if not edge:
        raise RouteGraphError("Линия маршрута не найдена")
    session.delete(edge)
    session.commit()


def clear_floor_graph(session: Session, floor_id: int) -> None:
    """Удалить все точки и линии маршрута на этаже после подтверждения пользователя."""
    ensure_floor_exists(session, floor_id)
    edges = session.exec(select(RouteEdge).where(RouteEdge.floor_id == floor_id)).all()
    nodes = session.exec(select(RouteNode).where(RouteNode.floor_id == floor_id)).all()
    for edge in edges:
        session.delete(edge)
    for node in nodes:
        session.delete(node)
    session.commit()


def find_shortest_path(
    session: Session,
    floor_id: int,
    start_node_id: int,
    end_node_id: int,
) -> RoutePath:
    """Найти кратчайший путь между двумя точками маршрута алгоритмом Дейкстры.

    Параметры:
        session: сессия работы с базой данных.
        floor_id: этаж, граф которого используется.
        start_node_id: id начальной точки маршрута.
        end_node_id: id конечной точки маршрута.

    Возвращает:
        Упорядоченные точки, упорядоченные линии и общая длина в пикселях.

    Ошибки:
        RouteGraphError: если этаж или выбранные точки не существуют.
        RouteNotFoundError: если точки есть, но путь между ними отсутствует.
    """
    ensure_floor_exists(session, floor_id)
    if start_node_id == end_node_id:
        node = session.get(RouteNode, start_node_id)
        if not node or node.floor_id != floor_id:
            raise RouteGraphError("Стартовая точка не найдена на выбранном этаже")
        return RoutePath(nodes=[node], edges=[], distance=0.0)

    nodes = session.exec(select(RouteNode).where(RouteNode.floor_id == floor_id)).all()
    edges = session.exec(select(RouteEdge).where(RouteEdge.floor_id == floor_id)).all()
    nodes_by_id = {node.id: node for node in nodes if node.id is not None}
    edges_by_id = {edge.id: edge for edge in edges if edge.id is not None}

    if start_node_id not in nodes_by_id:
        raise RouteGraphError("Стартовая точка не найдена на выбранном этаже")
    if end_node_id not in nodes_by_id:
        raise RouteGraphError("Конечная точка не найдена на выбранном этаже")

    adjacency: dict[int, list[tuple[int, float, int]]] = {node_id: [] for node_id in nodes_by_id}
    for edge in edges:
        if edge.id is None:
            continue
        adjacency.setdefault(edge.from_node_id, []).append((edge.to_node_id, edge.weight, edge.id))
        if edge.is_bidirectional:
            adjacency.setdefault(edge.to_node_id, []).append((edge.from_node_id, edge.weight, edge.id))

    distances: dict[int, float] = {start_node_id: 0.0}
    previous: dict[int, tuple[int, int]] = {}
    visited: set[int] = set()
    queue: list[tuple[float, int]] = [(0.0, start_node_id)]

    while queue:
        current_distance, current_node_id = heapq.heappop(queue)
        if current_node_id in visited:
            continue
        visited.add(current_node_id)

        if current_node_id == end_node_id:
            break

        for next_node_id, edge_weight, edge_id in adjacency.get(current_node_id, []):
            if next_node_id in visited:
                continue
            next_distance = current_distance + edge_weight
            if next_distance < distances.get(next_node_id, math.inf):
                distances[next_node_id] = next_distance
                previous[next_node_id] = (current_node_id, edge_id)
                heapq.heappush(queue, (next_distance, next_node_id))

    if end_node_id not in distances:
        raise RouteNotFoundError("Маршрут между выбранными точками не найден")

    path_node_ids = [end_node_id]
    path_edge_ids: list[int] = []
    current_node_id = end_node_id
    while current_node_id != start_node_id:
        previous_node_id, edge_id = previous[current_node_id]
        path_node_ids.append(previous_node_id)
        path_edge_ids.append(edge_id)
        current_node_id = previous_node_id

    path_node_ids.reverse()
    path_edge_ids.reverse()

    return RoutePath(
        nodes=[nodes_by_id[node_id] for node_id in path_node_ids],
        edges=[edges_by_id[edge_id] for edge_id in path_edge_ids],
        distance=distances[end_node_id],
    )
