from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
import os
from pathlib import Path
import shutil
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import cv2
import numpy as np
from sqlmodel import Session, select

from app.core.config import settings
from app.models.guests import Guest
from app.services.recognition_service import cosine_distance

_torch_import_error: Exception | None = None
_yolo_import_error: Exception | None = None
_torchreid_import_error: Exception | None = None

try:
    import torch
except Exception as exc:
    torch = None
    _torch_import_error = exc

try:
    from ultralytics import YOLO
except Exception as exc:
    YOLO = None
    _yolo_import_error = exc

try:
    from torchreid.utils import FeatureExtractor
except Exception as exc:
    try:
        from torchreid.reid.utils.feature_extractor import FeatureExtractor
    except Exception as fallback_exc:
        FeatureExtractor = None
        _torchreid_import_error = fallback_exc
    else:
        _torchreid_import_error = exc


logger = logging.getLogger(__name__)

_service_init_lock = threading.Lock()
_service_infer_lock = threading.Lock()
_person_detector = None
_feature_extractor = None
_detector_initialization_error: Exception | None = None
_extractor_initialization_error: Exception | None = None
_availability_warning_logged = False
_model_cache_configured = False


@dataclass(frozen=True)
class BodyDetection:
    bbox: tuple[int, int, int, int]
    confidence: float
    blur_score: float
    embedding: list[float]


@dataclass(frozen=True)
class GuestBodyMatch:
    guest: Guest
    distance: float
    similarity: float
    detection: BodyDetection


@dataclass(frozen=True)
class PersonPresenceDetection:
    bbox: tuple[int, int, int, int]
    confidence: float


def _normalize_embedding(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    if norm == 0:
        raise ValueError("Получен нулевой body embedding")
    return vector / norm


def _resolve_reid_device() -> str:
    if settings.reid_device and settings.reid_device != "auto":
        return settings.reid_device
    if torch is not None and torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _resolve_model_file_path(value: str, fallback_name: str) -> Path:
    configured = (value or fallback_name).strip()
    path = Path(configured).expanduser()
    if path.is_absolute():
        return path
    return settings.models_path / path


def _download_file(url: str, target_path: Path, label: str) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target_path.with_name(f"{target_path.name}.download")
    last_error: Exception | None = None

    for attempt in range(1, 4):
        try:
            request = Request(
                url,
                headers={"User-Agent": "biometric-access-control/1.0"},
            )
            with urlopen(request, timeout=120) as response:
                status = getattr(response, "status", 200)
                if status >= 400:
                    raise RuntimeError(f"HTTP {status}")
                with tmp_path.open("wb") as output:
                    shutil.copyfileobj(response, output)

            if tmp_path.stat().st_size == 0:
                raise RuntimeError("скачанный файл пустой")

            tmp_path.replace(target_path)
            logger.info("%s скачан в %s", label, target_path)
            return
        except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as exc:
            last_error = exc
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
            if attempt < 3:
                time.sleep(float(attempt))

    raise RuntimeError(f"Не удалось скачать {label} из {url}: {last_error}")


def _ensure_downloaded_model(
    target_path: Path,
    url: str,
    label: str,
    url_env_name: str,
) -> Path:
    if target_path.exists() and target_path.stat().st_size > 0:
        return target_path

    if not url:
        raise RuntimeError(
            f"{label} не найден: {target_path}. "
            f"Положите файл вручную или задайте {url_env_name}."
        )

    logger.info("%s не найден, скачиваю в %s", label, target_path)
    _download_file(url, target_path, label)
    return target_path


def _configure_model_cache() -> None:
    global _model_cache_configured

    if _model_cache_configured:
        return

    settings.models_path.mkdir(parents=True, exist_ok=True)
    settings.reid_torch_cache_path.mkdir(parents=True, exist_ok=True)
    os.environ["TORCH_HOME"] = str(settings.reid_torch_cache_path)
    os.environ.setdefault("XDG_CACHE_HOME", str(settings.models_path / "cache"))
    if torch is not None:
        torch.hub.set_dir(str(settings.reid_torch_cache_path / "hub"))

    _model_cache_configured = True


def _log_unavailable_once(reason: str) -> None:
    global _availability_warning_logged
    if _availability_warning_logged:
        return
    _availability_warning_logged = True
    logger.warning("Re-ID сервис недоступен: %s", reason)


def _ensure_feature_extractor_ready() -> bool:
    global _feature_extractor, _extractor_initialization_error

    if not settings.reid_enabled:
        _log_unavailable_once("REID_ENABLED=false")
        return False

    missing = []
    if torch is None:
        missing.append(f"torch ({_torch_import_error})")
    if FeatureExtractor is None:
        missing.append(f"torchreid ({_torchreid_import_error})")
    if missing:
        _log_unavailable_once(f"не установлены зависимости: {', '.join(missing)}")
        return False

    if _feature_extractor is not None:
        return True

    if _extractor_initialization_error is not None:
        return False

    with _service_init_lock:
        if _feature_extractor is not None:
            return True
        if _extractor_initialization_error is not None:
            return False

        try:
            _configure_model_cache()
            extractor_kwargs = {
                "model_name": settings.reid_model_name,
                "device": _resolve_reid_device(),
            }
            if settings.reid_model_path:
                reid_model_path = _ensure_downloaded_model(
                    _resolve_model_file_path(
                        settings.reid_model_path,
                        f"{settings.reid_model_name}.pth",
                    ),
                    settings.reid_model_url,
                    "OSNet Re-ID model",
                    "REID_MODEL_URL",
                )
                extractor_kwargs["model_path"] = str(reid_model_path)
            _feature_extractor = FeatureExtractor(**extractor_kwargs)
            logger.info(
                "Re-ID extractor инициализирован: model=%s, torch_cache=%s, device=%s",
                settings.reid_model_name,
                settings.reid_torch_cache_path,
                extractor_kwargs["device"],
            )
            return True
        except Exception as exc:
            _extractor_initialization_error = exc
            logger.exception("Не удалось инициализировать Re-ID extractor")
            return False


def _ensure_person_detector_ready() -> bool:
    global _person_detector, _detector_initialization_error

    if YOLO is None:
        _log_unavailable_once(f"не установлена зависимость: ultralytics ({_yolo_import_error})")
        return False

    if _person_detector is not None:
        return True

    if _detector_initialization_error is not None:
        return False

    with _service_init_lock:
        if _person_detector is not None:
            return True
        if _detector_initialization_error is not None:
            return False

        try:
            _configure_model_cache()
            detector_weights_path = _ensure_downloaded_model(
                _resolve_model_file_path(settings.reid_detector_weights, "yolo26n-pose.pt"),
                settings.reid_detector_url,
                "YOLO person/pose detector",
                "REID_DETECTOR_URL",
            )

            # YOLO детектирует person bbox, а TorchReID строит embedding по crop тела.
            _person_detector = YOLO(str(detector_weights_path))
            logger.info(
                "Re-ID detector инициализирован: detector=%s",
                detector_weights_path,
            )
            return True
        except Exception as exc:
            _detector_initialization_error = exc
            logger.exception("Не удалось инициализировать Re-ID detector")
            return False


def _ensure_reid_ready() -> bool:
    return _ensure_person_detector_ready() and _ensure_feature_extractor_ready()


def _clip_bbox(
    bbox: tuple[int, int, int, int],
    frame_shape: tuple[int, int, int],
) -> tuple[int, int, int, int] | None:
    frame_h, frame_w = frame_shape[:2]
    x1, y1, x2, y2 = bbox
    x1 = max(0, min(int(x1), frame_w - 1))
    y1 = max(0, min(int(y1), frame_h - 1))
    x2 = max(0, min(int(x2), frame_w))
    y2 = max(0, min(int(y2), frame_h))
    if x2 - x1 < 2 or y2 - y1 < 2:
        return None
    return x1, y1, x2, y2


def _bbox_area(bbox: tuple[int, int, int, int]) -> int:
    x1, y1, x2, y2 = bbox
    return max(0, x2 - x1) * max(0, y2 - y1)


def _validate_crop(
    crop_bgr: np.ndarray,
    bbox: tuple[int, int, int, int],
    frame_shape: tuple[int, int, int],
) -> float:
    crop_h, crop_w = crop_bgr.shape[:2]
    if crop_w < settings.reid_min_crop_width or crop_h < settings.reid_min_crop_height:
        raise ValueError("силуэт слишком маленький для Re-ID")

    frame_area = frame_shape[0] * frame_shape[1]
    if frame_area <= 0 or (_bbox_area(bbox) / frame_area) < settings.reid_min_area_ratio:
        raise ValueError("силуэт занимает слишком мало площади кадра")

    if crop_h <= crop_w:
        raise ValueError("силуэт слишком сильно обрезан по высоте")

    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if blur_score < settings.reid_blur_threshold:
        raise ValueError("силуэт слишком смазан")

    x1, y1, x2, y2 = bbox
    touches_border = x1 <= 1 or y1 <= 1 or x2 >= frame_shape[1] - 1 or y2 >= frame_shape[0] - 1
    if touches_border and (
        crop_w < int(settings.reid_min_crop_width * 1.25)
        or crop_h < int(settings.reid_min_crop_height * 1.25)
    ):
        raise ValueError("силуэт заметно обрезан границей кадра")

    return blur_score


def _detect_person_boxes(
    frame_bgr: np.ndarray,
    *,
    confidence: float | None = None,
) -> list[tuple[tuple[int, int, int, int], float]]:
    if not _ensure_person_detector_ready():
        return []

    threshold = settings.reid_person_confidence if confidence is None else confidence
    with _service_infer_lock:
        results = _person_detector.predict(
            source=frame_bgr,
            classes=[0],
            conf=threshold,
            verbose=False,
        )

    if not results:
        return []

    boxes = getattr(results[0], "boxes", None)
    if boxes is None or boxes.xyxy is None:
        return []

    coords = boxes.xyxy.cpu().numpy()
    confidences = boxes.conf.cpu().numpy() if boxes.conf is not None else np.ones(len(coords))

    detections: list[tuple[tuple[int, int, int, int], float]] = []
    for raw_box, confidence in zip(coords, confidences):
        clipped = _clip_bbox(
            tuple(int(round(value)) for value in raw_box[:4]),
            frame_bgr.shape,
        )
        if clipped is None:
            continue
        detections.append((clipped, float(confidence)))

    detections.sort(key=lambda item: (_bbox_area(item[0]), item[1]), reverse=True)
    return detections


def detect_person_presence(
    frame_bgr: np.ndarray,
    *,
    confidence: float | None = None,
) -> list[PersonPresenceDetection] | None:
    """Fast YOLO trigger used before expensive InsightFace/Re-ID analysis."""
    if frame_bgr is None or frame_bgr.size == 0:
        return []

    if not _ensure_person_detector_ready():
        return None

    threshold = settings.analysis_trigger_person_confidence
    if confidence is not None:
        threshold = confidence

    detections = [
        PersonPresenceDetection(bbox=bbox, confidence=score)
        for bbox, score in _detect_person_boxes(frame_bgr, confidence=threshold)
        if score >= threshold
    ]
    return detections


def extract_body_detections(frame_bgr: np.ndarray) -> list[BodyDetection]:
    if frame_bgr is None or frame_bgr.size == 0:
        return []

    if not _ensure_reid_ready():
        return []

    detections = _detect_person_boxes(frame_bgr)
    if not detections:
        return []

    valid_items: list[tuple[tuple[int, int, int, int], float, float]] = []
    crops_rgb: list[np.ndarray] = []

    for bbox, confidence in detections:
        x1, y1, x2, y2 = bbox
        crop_bgr = frame_bgr[y1:y2, x1:x2]
        try:
            blur_score = _validate_crop(crop_bgr, bbox, frame_bgr.shape)
        except ValueError as exc:
            logger.debug("Re-ID пропускает bbox=%s: %s", bbox, exc)
            continue

        # PyAV/OpenCV pipeline отдает BGR, а TorchReID ожидает RGB вход.
        crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
        crops_rgb.append(crop_rgb)
        valid_items.append((bbox, confidence, blur_score))

    if not valid_items:
        return []

    with _service_infer_lock:
        features = _feature_extractor(crops_rgb)

    if hasattr(features, "cpu"):
        features = features.cpu().numpy()

    body_detections: list[BodyDetection] = []
    for (bbox, confidence, blur_score), feature in zip(valid_items, features):
        vector = _normalize_embedding(np.asarray(feature, dtype=np.float32))
        body_detections.append(
            BodyDetection(
                bbox=bbox,
                confidence=confidence,
                blur_score=blur_score,
                embedding=vector.tolist(),
            )
        )

    return body_detections


def extract_body_embedding_from_crop(
    crop_bgr: np.ndarray,
    *,
    validate_crop: bool = True,
) -> list[float] | None:
    """Build a Re-ID embedding from an already cropped person image.

    This is useful for enrollment: an operator can provide a person/body photo
    when face recognition is not reliable enough for issuing a pass.
    """
    if crop_bgr is None or crop_bgr.size == 0:
        return None

    if not _ensure_feature_extractor_ready():
        return None

    crop_h, crop_w = crop_bgr.shape[:2]
    if validate_crop:
        try:
            _validate_crop(crop_bgr, (0, 0, crop_w, crop_h), crop_bgr.shape)
        except ValueError as exc:
            logger.debug("Re-ID enrollment crop rejected: %s", exc)
            return None

    # PyAV/OpenCV pipeline keeps frames in BGR, while TorchReID expects RGB.
    crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    with _service_infer_lock:
        features = _feature_extractor([crop_rgb])

    if hasattr(features, "cpu"):
        features = features.cpu().numpy()

    if len(features) == 0:
        return None

    vector = _normalize_embedding(np.asarray(features[0], dtype=np.float32))
    return vector.tolist()


def extract_body_embedding_from_image_bytes(
    image_bytes: bytes,
    *,
    validate_crop: bool = True,
) -> list[float] | None:
    if not image_bytes:
        return None

    encoded = np.frombuffer(image_bytes, dtype=np.uint8)
    crop_bgr = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if crop_bgr is None:
        return None

    return extract_body_embedding_from_crop(crop_bgr, validate_crop=validate_crop)


def extract_primary_body_embedding_from_image_bytes(
    image_bytes: bytes,
) -> list[float] | None:
    """Extract a body embedding from either a person crop or a full camera frame."""
    if not image_bytes:
        return None

    encoded = np.frombuffer(image_bytes, dtype=np.uint8)
    frame_bgr = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if frame_bgr is None:
        return None

    crop_embedding = extract_body_embedding_from_crop(frame_bgr)
    if crop_embedding is not None:
        return crop_embedding

    detections = extract_body_detections(frame_bgr)
    if not detections:
        return None

    # Detections are sorted by person bbox area/confidence in _detect_person_boxes.
    return detections[0].embedding


def _bbox_iou(
    box_a: tuple[int, int, int, int],
    box_b: tuple[int, int, int, int],
) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_area = _bbox_area((inter_x1, inter_y1, inter_x2, inter_y2))
    if inter_area <= 0:
        return 0.0
    union = _bbox_area(box_a) + _bbox_area(box_b) - inter_area
    return inter_area / union if union > 0 else 0.0


def _select_detection_for_face(
    detections: list[BodyDetection],
    face_bbox: tuple[int, int, int, int],
) -> BodyDetection | None:
    face_center_x = (face_bbox[0] + face_bbox[2]) / 2.0
    face_center_y = (face_bbox[1] + face_bbox[3]) / 2.0

    containing = [
        detection
        for detection in detections
        if detection.bbox[0] <= face_center_x <= detection.bbox[2]
        and detection.bbox[1] <= face_center_y <= detection.bbox[3]
    ]
    if containing:
        # Если лицо попало внутрь нескольких person bbox, берем самый компактный.
        return min(containing, key=lambda detection: _bbox_area(detection.bbox))

    return max(detections, key=lambda detection: _bbox_iou(detection.bbox, face_bbox), default=None)


def extract_body_detection_for_face(
    frame_bgr: np.ndarray,
    face_bbox: tuple[int, int, int, int],
) -> BodyDetection | None:
    detections = extract_body_detections(frame_bgr)
    if not detections:
        return None
    return _select_detection_for_face(detections, face_bbox)


def _load_active_guest_embeddings(session: Session) -> list[tuple[Guest, np.ndarray]]:
    guests = session.exec(
        select(Guest).where(
            Guest.is_active.is_(True),
            Guest.valid_until > datetime.now(),
        )
    ).all()

    active_embeddings: list[tuple[Guest, np.ndarray]] = []
    for guest in guests:
        if not guest.body_embedding:
            continue
        try:
            vector = _normalize_embedding(np.asarray(guest.body_embedding, dtype=np.float32))
        except ValueError:
            continue
        active_embeddings.append((guest, vector))

    return active_embeddings


def match_guest_by_body(
    frame_bgr: np.ndarray,
    session: Session,
) -> GuestBodyMatch | None:
    guest_embeddings = _load_active_guest_embeddings(session)
    if not guest_embeddings:
        return None

    detections = extract_body_detections(frame_bgr)
    if not detections:
        return None

    best_match: GuestBodyMatch | None = None
    for detection in detections:
        vector_a = np.asarray(detection.embedding, dtype=np.float32)
        for guest, vector_b in guest_embeddings:
            if vector_a.shape != vector_b.shape:
                continue

            distance = cosine_distance(vector_a, vector_b)
            if distance > settings.reid_match_distance:
                continue

            similarity = max(0.0, min(1.0, 1.0 - float(distance)))
            match = GuestBodyMatch(
                guest=guest,
                distance=float(distance),
                similarity=similarity,
                detection=detection,
            )
            if best_match is None or match.distance < best_match.distance:
                best_match = match

    return best_match


def update_guest_body_embedding(
    session: Session,
    guest: Guest,
    new_embedding: list[float],
) -> None:
    next_vector = _normalize_embedding(np.asarray(new_embedding, dtype=np.float32))

    if guest.body_embedding:
        try:
            current_vector = _normalize_embedding(np.asarray(guest.body_embedding, dtype=np.float32))
            if current_vector.shape == next_vector.shape:
                # EMA сглаживает шум позы/освещения, но позволяет адаптироваться к смене одежды.
                alpha = min(max(settings.reid_update_alpha, 0.0), 1.0)
                next_vector = _normalize_embedding(
                    ((1.0 - alpha) * current_vector) + (alpha * next_vector)
                )
        except ValueError:
            pass

    guest.body_embedding = next_vector.tolist()
    guest.body_embedding_updated_at = datetime.now()
    session.add(guest)


def update_guest_body_embedding_from_frame(
    session: Session,
    guest: Guest,
    frame_bgr: np.ndarray,
    face_bbox: tuple[int, int, int, int],
) -> BodyDetection | None:
    detection = extract_body_detection_for_face(frame_bgr, face_bbox)
    if detection is None:
        return None

    update_guest_body_embedding(session, guest, detection.embedding)
    return detection
