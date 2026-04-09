import os

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import platform
import threading

import cv2
import numpy as np
import onnxruntime as ort
from insightface.app import FaceAnalysis


_face_app = None
_face_app_init_lock = threading.Lock()
_face_app_infer_lock = threading.Lock()


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

    print("InsightFace providers:", providers)
    print("ORT available providers:", ort.get_available_providers())

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


def extract_face_encoding(image_bytes: bytes) -> list[float]:
    image = decode_image_bytes(image_bytes)
    app = get_face_app()

    with _face_app_infer_lock:
        faces = app.get(image)

    if not faces:
        raise ValueError("Лицо не найдено")

    best_face = max(
        faces,
        key=lambda face: float((face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1]))
    )

    emb = getattr(best_face, "normed_embedding", None)
    if emb is None:
        emb = np.asarray(best_face.embedding, dtype=np.float32)
        norm = np.linalg.norm(emb)
        if norm == 0:
            raise ValueError("Получен нулевой embedding")
        emb = emb / norm
    else:
        emb = np.asarray(emb, dtype=np.float32)

    return emb.tolist()