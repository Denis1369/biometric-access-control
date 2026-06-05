"""Преобразование фотографии лица в embedding InsightFace.

Этот сервис используется при создании сотрудника, создании гостя и загрузке
дополнительных фотографий. Пользователь загружает обычное изображение, backend
декодирует его через OpenCV, передаёт в InsightFace, выбирает самое крупное лицо
и сохраняет нормализованный числовой вектор. Позже recognition_service сравнит
этот вектор с лицом из кадра камеры.

ONNXRuntime используется под капотом InsightFace для запуска нейросетевой модели.
Провайдер выбирается автоматически: если доступен CUDAExecutionProvider, модель
может работать на GPU, иначе используется CPUExecutionProvider.
"""

import os

os.environ.setdefault("NO_ALBUMENTATIONS_UPDATE", "1")

from app.core.config import settings

thread_count = str(settings.ml_thread_count)

os.environ["OMP_NUM_THREADS"] = thread_count
os.environ["OPENBLAS_NUM_THREADS"] = thread_count
os.environ["MKL_NUM_THREADS"] = thread_count
os.environ["VECLIB_MAXIMUM_THREADS"] = thread_count
os.environ["NUMEXPR_NUM_THREADS"] = thread_count

import logging
import threading
from typing import Any

import cv2
import numpy as np


_face_app: Any | None = None
_face_app_init_lock = threading.Lock()
_face_app_infer_lock = threading.Lock()
logger = logging.getLogger(__name__)


def _get_onnxruntime():
    """Лениво импортировать ONNXRuntime.

    Импорт вынесен в функцию, чтобы окружение и лимиты потоков были настроены до
    загрузки библиотеки. Это снижает риск, что ONNXRuntime или BLAS создадут
    слишком много потоков на слабом компьютере.
    """

    import onnxruntime as ort

    return ort


def _choose_providers() -> list[str]:
    """Выбрать доступные backend-ы выполнения модели InsightFace.

    Если установлен GPU-провайдер CUDA, он ставится первым, а CPU остаётся
    fallback-ом. На обычном ноутбуке без CUDA будет выбран CPUExecutionProvider.
    """

    ort = _get_onnxruntime()
    available = set(ort.get_available_providers())

    if "CUDAExecutionProvider" in available:
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]

    return ["CPUExecutionProvider"]


def _build_face_app():
    """Инициализировать приложение InsightFace.

    FaceAnalysis загружает модель `buffalo_l`, подготавливает детектор лица и
    модель embedding-а. ctx_id равен 0 для GPU и -1 для CPU. Эта операция тяжёлая,
    поэтому приложение создаётся один раз и переиспользуется.
    """

    from insightface.app import FaceAnalysis

    ort = _get_onnxruntime()
    providers = _choose_providers()
    app = FaceAnalysis(name="buffalo_l", providers=providers)

    # ctx_id=0 для GPU, -1 для CPU
    ctx_id = -1 if providers == ["CPUExecutionProvider"] else 0
    app.prepare(ctx_id=ctx_id, det_size=(640, 640))

    logger.info("InsightFace providers: %s", providers)
    logger.info("ORT available providers: %s", ort.get_available_providers())

    return app


def get_face_app():
    """Вернуть singleton InsightFace FaceAnalysis.

    Двойная проверка с lock нужна, чтобы при одновременных запросах несколько
    потоков не начали загружать тяжёлую модель параллельно. После первого
    успешного создания все вызовы возвращают один и тот же объект.
    """

    global _face_app
    if _face_app is None:
        with _face_app_init_lock:
            if _face_app is None:
                _face_app = _build_face_app()
    return _face_app


def decode_image_bytes(image_bytes: bytes) -> np.ndarray:
    """Декодировать загруженные байты изображения в BGR-массив OpenCV.

    Параметры:
        image_bytes: Содержимое файла, пришедшего из multipart/form-data.

    Возвращает:
        np.ndarray в формате BGR, который ожидают OpenCV и InsightFace.

    Ошибки:
        ValueError: Если файл не является корректным изображением.
    """

    np_arr = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Не удалось декодировать изображение")
    return image


def _normalize_embedding(embedding: np.ndarray) -> np.ndarray:
    """Нормализовать embedding лица до единичной длины.

    Нормализация нужна, чтобы сравнение cosine distance было стабильным и не
    зависело от абсолютного масштаба вектора.
    """

    norm = np.linalg.norm(embedding)
    if norm == 0:
        raise ValueError("Получен нулевой embedding")
    return embedding / norm


def _extract_face_embedding(face) -> np.ndarray:
    """Достать embedding из объекта лица InsightFace.

    InsightFace обычно отдаёт `normed_embedding`, уже готовый к сравнению. Если
    его нет, берётся обычный embedding и нормализуется вручную.
    """

    emb = getattr(face, "normed_embedding", None)
    if emb is None:
        emb = np.asarray(face.embedding, dtype=np.float32)
        return _normalize_embedding(emb)
    return np.asarray(emb, dtype=np.float32)


def _get_best_face(image_bgr: np.ndarray):
    """Найти самое крупное лицо на изображении.

    Если на фото несколько лиц, выбирается лицо с максимальной площадью bbox.
    Для карточки сотрудника или гостя это обычно главное лицо на фотографии.

    Ошибки:
        ValueError: Если InsightFace не нашёл ни одного лица.
    """

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
    """Получить face embedding из уже декодированного BGR-изображения."""

    best_face = _get_best_face(image_bgr)
    return _extract_face_embedding(best_face).tolist()


def extract_face_encoding_with_bbox_from_bgr(
    image_bgr: np.ndarray,
) -> tuple[list[float], tuple[int, int, int, int]]:
    """Получить face embedding и координаты лица на кадре.

    Эта версия нужна для видеоанализа: кроме самого вектора полезно знать bbox,
    чтобы вырезать preview или показать, где в кадре было найдено лицо.
    """

    best_face = _get_best_face(image_bgr)
    bbox = tuple(int(round(value)) for value in best_face.bbox[:4])
    return _extract_face_embedding(best_face).tolist(), bbox


def extract_face_encoding(image_bytes: bytes) -> list[float]:
    """Получить face embedding из загруженных байтов изображения.

    Это главный публичный helper для API создания сотрудника/гостя: он принимает
    файл из формы, декодирует изображение, находит лицо и возвращает числовой
    вектор, который затем сохраняется в employee_face_samples или
    guest_face_samples.
    """

    image = decode_image_bytes(image_bytes)
    return extract_face_encoding_from_bgr(image)
