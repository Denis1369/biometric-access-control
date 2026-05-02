from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import mean, median
from typing import Literal

from sqlmodel import Session, select

from app.models.cameras import Camera
from app.models.logs import AccessLog, TrackingLog

PersonType = Literal["all", "employee", "guest"]


@dataclass(frozen=True)
class CameraTimelineEvent:
    person_key: str
    camera_id: int
    camera_name: str
    timestamp: datetime
    confidence: float


@dataclass
class CameraTransitionAggregate:
    from_camera_id: int
    from_camera_name: str
    to_camera_id: int
    to_camera_name: str
    travel_seconds: list[float] = field(default_factory=list)
    person_keys: set[str] = field(default_factory=set)

    def add(self, person_key: str, seconds: float) -> None:
        self.person_keys.add(person_key)
        self.travel_seconds.append(seconds)

    @property
    def transition_count(self) -> int:
        return len(self.travel_seconds)

    @property
    def unique_person_count(self) -> int:
        return len(self.person_keys)


@dataclass(frozen=True)
class CameraTransition:
    from_camera_id: int
    from_camera_name: str
    to_camera_id: int
    to_camera_name: str
    transition_count: int
    unique_person_count: int
    avg_travel_seconds: float
    median_travel_seconds: float
    min_travel_seconds: float
    max_travel_seconds: float
    confidence: float


def _person_key(employee_id: int | None, guest_id: int | None, person_type: PersonType) -> str | None:
    if guest_id is not None and person_type in ("all", "guest"):
        return f"guest:{guest_id}"
    if employee_id is not None and person_type in ("all", "employee"):
        return f"employee:{employee_id}"
    return None


def _camera_filter(statement, building_id: int | None, floor_id: int | None):
    if building_id is not None:
        statement = statement.where(Camera.building_id == building_id)
    if floor_id is not None:
        statement = statement.where(Camera.floor_id == floor_id)
    return statement


def _load_timeline_events(
    session: Session,
    *,
    start_at: datetime,
    end_at: datetime,
    person_type: PersonType,
    building_id: int | None,
    floor_id: int | None,
) -> list[CameraTimelineEvent]:
    events: list[CameraTimelineEvent] = []

    tracking_statement = (
        select(TrackingLog, Camera)
        .join(Camera, TrackingLog.camera_id == Camera.id)
        .where(TrackingLog.timestamp >= start_at)
        .where(TrackingLog.timestamp <= end_at)
        .where(TrackingLog.camera_id.is_not(None))
    )
    tracking_statement = _camera_filter(tracking_statement, building_id, floor_id)

    access_statement = (
        select(AccessLog, Camera)
        .join(Camera, AccessLog.camera_id == Camera.id)
        .where(AccessLog.timestamp >= start_at)
        .where(AccessLog.timestamp <= end_at)
        .where(AccessLog.status == "granted")
        .where(AccessLog.camera_id.is_not(None))
    )
    access_statement = _camera_filter(access_statement, building_id, floor_id)

    for log, camera in session.exec(tracking_statement).all():
        person_key = _person_key(log.employee_id, log.guest_id, person_type)
        if person_key is None or camera.id is None:
            continue
        events.append(
            CameraTimelineEvent(
                person_key=person_key,
                camera_id=camera.id,
                camera_name=camera.name,
                timestamp=log.timestamp,
                confidence=float(log.confidence),
            )
        )

    for log, camera in session.exec(access_statement).all():
        person_key = _person_key(log.employee_id, log.guest_id, person_type)
        if person_key is None or camera.id is None:
            continue
        events.append(
            CameraTimelineEvent(
                person_key=person_key,
                camera_id=camera.id,
                camera_name=camera.name,
                timestamp=log.timestamp,
                confidence=float(log.confidence or 1.0),
            )
        )

    events.sort(key=lambda item: (item.person_key, item.timestamp, item.camera_id))
    return events


def _transition_confidence(
    *,
    transition_count: int,
    unique_person_count: int,
    outgoing_count: int,
    reliable_transition_count: int,
) -> float:
    if outgoing_count <= 0:
        return 0.0

    probability = transition_count / outgoing_count
    support = min(1.0, (transition_count / max(reliable_transition_count, 1)) ** 0.5)
    people_support = min(1.0, unique_person_count / 3)
    return round(probability * ((0.75 * support) + (0.25 * people_support)), 3)


def infer_camera_transitions(
    session: Session,
    *,
    start_at: datetime,
    end_at: datetime,
    person_type: PersonType = "all",
    building_id: int | None = None,
    floor_id: int | None = None,
    max_transition_gap: timedelta = timedelta(minutes=30),
    min_transition_count: int = 1,
    reliable_transition_count: int = 5,
    limit: int = 100,
) -> list[CameraTransition]:
    events = _load_timeline_events(
        session,
        start_at=start_at,
        end_at=end_at,
        person_type=person_type,
        building_id=building_id,
        floor_id=floor_id,
    )

    events_by_person: dict[str, list[CameraTimelineEvent]] = defaultdict(list)
    for event in events:
        events_by_person[event.person_key].append(event)

    aggregates: dict[tuple[int, int], CameraTransitionAggregate] = {}
    outgoing_counts: dict[int, int] = defaultdict(int)

    for person_key, person_events in events_by_person.items():
        previous: CameraTimelineEvent | None = None

        for event in person_events:
            if previous is None:
                previous = event
                continue

            if event.camera_id == previous.camera_id:
                # Для handoff важен последний момент, когда человек был виден на прошлой камере.
                previous = event
                continue

            gap = event.timestamp - previous.timestamp
            if timedelta(0) < gap <= max_transition_gap:
                edge_key = (previous.camera_id, event.camera_id)
                aggregate = aggregates.get(edge_key)
                if aggregate is None:
                    aggregate = CameraTransitionAggregate(
                        from_camera_id=previous.camera_id,
                        from_camera_name=previous.camera_name,
                        to_camera_id=event.camera_id,
                        to_camera_name=event.camera_name,
                    )
                    aggregates[edge_key] = aggregate

                aggregate.add(person_key, gap.total_seconds())
                outgoing_counts[previous.camera_id] += 1

            previous = event

    transitions: list[CameraTransition] = []
    for aggregate in aggregates.values():
        if aggregate.transition_count < min_transition_count:
            continue

        travel_seconds = aggregate.travel_seconds
        transitions.append(
            CameraTransition(
                from_camera_id=aggregate.from_camera_id,
                from_camera_name=aggregate.from_camera_name,
                to_camera_id=aggregate.to_camera_id,
                to_camera_name=aggregate.to_camera_name,
                transition_count=aggregate.transition_count,
                unique_person_count=aggregate.unique_person_count,
                avg_travel_seconds=round(mean(travel_seconds), 1),
                median_travel_seconds=round(median(travel_seconds), 1),
                min_travel_seconds=round(min(travel_seconds), 1),
                max_travel_seconds=round(max(travel_seconds), 1),
                confidence=_transition_confidence(
                    transition_count=aggregate.transition_count,
                    unique_person_count=aggregate.unique_person_count,
                    outgoing_count=outgoing_counts[aggregate.from_camera_id],
                    reliable_transition_count=reliable_transition_count,
                ),
            )
        )

    transitions.sort(
        key=lambda item: (
            item.confidence,
            item.transition_count,
            item.unique_person_count,
            -item.median_travel_seconds,
        ),
        reverse=True,
    )
    return transitions[: max(1, limit)]
