from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Field, SQLModel, Session

from app.core.database import get_session
from app.core.deps import require_roles
from app.models.route_edges import RouteEdge
from app.models.route_nodes import RouteNode
from app.models.user import UserRole
from app.services.route_graph_service import (
    RouteGraphError,
    RouteNotFoundError,
    clear_floor_graph,
    create_route_edge,
    create_route_node,
    delete_route_edge,
    delete_route_node,
    find_shortest_path,
    get_floor_graph,
    update_route_node,
)

router = APIRouter(prefix="/api", tags=["Граф маршрутов"])

READ_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.CHECKPOINT_OPERATOR,
)
WRITE_ROLES = (
    UserRole.SUPER_ADMIN,
)


class RouteNodeCreate(SQLModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)


class RouteNodeUpdate(SQLModel):
    x: float | None = Field(default=None, ge=0)
    y: float | None = Field(default=None, ge=0)


class RouteEdgeCreate(SQLModel):
    from_node_id: int
    to_node_id: int
    is_bidirectional: bool = True


class RoutePathRequest(SQLModel):
    start_node_id: int
    end_node_id: int


class RouteNodeRead(SQLModel):
    id: int
    floor_id: int
    x: float
    y: float
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RouteEdgeRead(SQLModel):
    id: int
    floor_id: int
    from_node_id: int
    to_node_id: int
    weight: float
    is_bidirectional: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RouteGraphRead(SQLModel):
    nodes: list[RouteNodeRead]
    edges: list[RouteEdgeRead]


class RoutePathNodeRead(SQLModel):
    id: int
    x: float
    y: float


class RoutePathEdgeRead(SQLModel):
    id: int
    from_node_id: int
    to_node_id: int
    weight: float


class RoutePathRead(SQLModel):
    nodes: list[RoutePathNodeRead]
    edges: list[RoutePathEdgeRead]
    distance: float


def _node_to_read(node: RouteNode) -> RouteNodeRead:
    return RouteNodeRead(
        id=node.id,
        floor_id=node.floor_id,
        x=node.x,
        y=node.y,
        created_at=node.created_at,
        updated_at=node.updated_at,
    )


def _edge_to_read(edge: RouteEdge) -> RouteEdgeRead:
    return RouteEdgeRead(
        id=edge.id,
        floor_id=edge.floor_id,
        from_node_id=edge.from_node_id,
        to_node_id=edge.to_node_id,
        weight=edge.weight,
        is_bidirectional=edge.is_bidirectional,
        created_at=edge.created_at,
        updated_at=edge.updated_at,
    )


def _raise_http_error(error: RouteGraphError):
    if isinstance(error, RouteNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(error),
    )


@router.get(
    "/floors/{floor_id}/route-graph",
    response_model=RouteGraphRead,
    summary="Получить граф маршрутов этажа",
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def get_route_graph(floor_id: int, session: Session = Depends(get_session)):
    try:
        nodes, edges = get_floor_graph(session, floor_id)
    except RouteGraphError as error:
        _raise_http_error(error)

    return RouteGraphRead(
        nodes=[_node_to_read(node) for node in nodes],
        edges=[_edge_to_read(edge) for edge in edges],
    )


@router.post(
    "/floors/{floor_id}/route-nodes",
    response_model=RouteNodeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать точку маршрута",
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
)
def create_node(
    floor_id: int,
    payload: RouteNodeCreate,
    session: Session = Depends(get_session),
):
    try:
        node = create_route_node(session, floor_id, payload.x, payload.y)
    except RouteGraphError as error:
        _raise_http_error(error)
    return _node_to_read(node)


@router.patch(
    "/route-nodes/{node_id}",
    response_model=RouteNodeRead,
    summary="Обновить координаты точки маршрута",
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
)
def update_node(
    node_id: int,
    payload: RouteNodeUpdate,
    session: Session = Depends(get_session),
):
    if payload.x is None and payload.y is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Передайте x или y для обновления точки",
        )

    try:
        node = update_route_node(session, node_id, payload.x, payload.y)
    except RouteGraphError as error:
        _raise_http_error(error)
    return _node_to_read(node)


@router.delete(
    "/route-nodes/{node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить точку маршрута",
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
)
def delete_node(node_id: int, session: Session = Depends(get_session)):
    try:
        delete_route_node(session, node_id)
    except RouteGraphError as error:
        _raise_http_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/floors/{floor_id}/route-edges",
    response_model=RouteEdgeRead,
    summary="Создать линию маршрута",
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
)
def create_edge(
    floor_id: int,
    payload: RouteEdgeCreate,
    session: Session = Depends(get_session),
):
    try:
        edge = create_route_edge(
            session=session,
            floor_id=floor_id,
            from_node_id=payload.from_node_id,
            to_node_id=payload.to_node_id,
            is_bidirectional=payload.is_bidirectional,
        )
    except RouteGraphError as error:
        _raise_http_error(error)
    return _edge_to_read(edge)


@router.delete(
    "/route-edges/{edge_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить линию маршрута",
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
)
def delete_edge(edge_id: int, session: Session = Depends(get_session)):
    try:
        delete_route_edge(session, edge_id)
    except RouteGraphError as error:
        _raise_http_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/floors/{floor_id}/route-graph",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Очистить граф маршрутов этажа",
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
)
def clear_graph(floor_id: int, session: Session = Depends(get_session)):
    try:
        clear_floor_graph(session, floor_id)
    except RouteGraphError as error:
        _raise_http_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/floors/{floor_id}/route-path",
    response_model=RoutePathRead,
    summary="Построить кратчайший маршрут по графу этажа",
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def build_route_path(
    floor_id: int,
    payload: RoutePathRequest,
    session: Session = Depends(get_session),
):
    try:
        path = find_shortest_path(
            session=session,
            floor_id=floor_id,
            start_node_id=payload.start_node_id,
            end_node_id=payload.end_node_id,
        )
    except RouteGraphError as error:
        _raise_http_error(error)

    return RoutePathRead(
        nodes=[
            RoutePathNodeRead(id=node.id, x=node.x, y=node.y)
            for node in path.nodes
        ],
        edges=[
            RoutePathEdgeRead(
                id=edge.id,
                from_node_id=edge.from_node_id,
                to_node_id=edge.to_node_id,
                weight=edge.weight,
            )
            for edge in path.edges
        ],
        distance=path.distance,
    )
