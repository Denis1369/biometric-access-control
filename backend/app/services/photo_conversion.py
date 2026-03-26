import io
import cv2
import numpy as np
from PIL import Image, ImageOps
from fastapi import HTTPException, status
from insightface.app import FaceAnalysis

face_app = FaceAnalysis(
    name="buffalo_l",
    providers=["CPUExecutionProvider"]
)
face_app.prepare(ctx_id=0, det_size=(640, 640))


def extract_face_encoding(image_bytes: bytes) -> list[float]:
    try:
        pil_img = Image.open(io.BytesIO(image_bytes))
        pil_img = ImageOps.exif_transpose(pil_img).convert("RGB")
        img = np.array(pil_img)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Не удалось прочитать изображение: {str(e)}"
        )

    faces = face_app.get(img)

    if len(faces) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Лицо не найдено на фотографии."
        )

    if len(faces) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="На фотографии найдено несколько лиц. Загрузите фото с одним человеком."
        )

    face = faces[0]

    embedding = face.normed_embedding.tolist()
    return embedding