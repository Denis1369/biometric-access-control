import os

from app.core.config import settings

thread_count = str(settings.ml_thread_count)

os.environ["OMP_NUM_THREADS"] = thread_count
os.environ["OPENBLAS_NUM_THREADS"] = thread_count
os.environ["MKL_NUM_THREADS"] = thread_count
os.environ["VECLIB_MAXIMUM_THREADS"] = thread_count
os.environ["NUMEXPR_NUM_THREADS"] = thread_count

import logging
import threading

import cv2
import numpy as np
import onnxruntime as ort
from insightface.app import FaceAnalysis


_face_app = None
_face_app_init_lock = threading.Lock()
_face_app_infer_lock = threading.Lock()
logger = logging.getLogger(__name__)


def _choose_providers() -> list[str]:
    available = set(ort.get_available_providers())

    if "CUDAExecutionProvider" in available:
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]

    return ["CPUExecutionProvider"]


def _build_face_app() -> FaceAnalysis:
    providers = _choose_providers()
    app = FaceAnalysis(name="buffalo_l", providers=providers)

    # ctx_id=0 для GPU, -1 для CPU
    ctx_id = -1 if providers == ["CPUExecutionProvider"] else 0
    app.prepare(ctx_id=ctx_id, det_size=(640, 640))

    logger.info("InsightFace providers: %s", providers)
    logger.info("ORT available providers: %s", ort.get_available_providers())

    return app


def get_face_app() -> FaceAnalysis:
    global _face_app
    if _face_app is None:
        with _face_app_init_lock:
            if _face_app is None:
                _face_app = _build_face_app()
    return _face_app


def decode_image_bytes(image_bytes: bytes) -> np.ndarray:
    np_arr = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Не удалось декодировать изображение")
    return image


def _normalize_embedding(embedding: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(embedding)
    if norm == 0:
        raise ValueError("Получен нулевой embedding")
    return embedding / norm


def _extract_face_embedding(face) -> np.ndarray:
    emb = getattr(face, "normed_embedding", None)
    if emb is None:
        emb = np.asarray(face.embedding, dtype=np.float32)
        return _normalize_embedding(emb)
    return np.asarray(emb, dtype=np.float32)


def _get_best_face(image_bgr: np.ndarray):
    app = get_face_app()

    with _face_app_infer_lock:
        faces = app.get(image_bgr)

    if not faces:
        raise ValueError("Лицо не найдено")

    return max(
        faces,
        key=lambda face: float((face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1]))
    )


def extract_face_encoding_from_bgr(image_bgr: np.ndarray) -> list[float]:
    best_face = _get_best_face(image_bgr)
    return _extract_face_embedding(best_face).tolist()


def extract_face_encoding_with_bbox_from_bgr(
    image_bgr: np.ndarray,
) -> tuple[list[float], tuple[int, int, int, int]]:
    best_face = _get_best_face(image_bgr)
    bbox = tuple(int(round(value)) for value in best_face.bbox[:4])
    return _extract_face_embedding(best_face).tolist(), bbox


def extract_face_encoding(image_bytes: bytes) -> list[float]:
    image = decode_image_bytes(image_bytes)
    return extract_face_encoding_from_bgr(image)
