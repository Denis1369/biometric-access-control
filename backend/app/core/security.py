"""Функции безопасности: пароли и JWT-токены.

Этот модуль не знает ничего о сотрудниках, гостях или камерах. Его задача
ниже уровнем: безопасно проверить пароль, создать хэш пароля, выпустить
access-token после входа и прочитать id пользователя из токена при следующих
запросах.

Пароль никогда не хранится в базе в открытом виде. В таблицу users записывается
только bcrypt-хэш, а JWT содержит минимальный subject — id пользователя.
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

SECRET_KEY = settings.jwt_secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Проверить пароль пользователя против сохранённого хэша.

    Параметры:
        plain_password: Пароль, который пользователь ввёл в форме входа.
        password_hash: Хэш из таблицы users.password_hash.

    Возвращает:
        True, если пароль соответствует хэшу. Сам пароль при этом не сохраняется
        и не возвращается.
    """

    return pwd_context.verify(plain_password, password_hash)


def get_password_hash(password: str) -> str:
    """Создать bcrypt-хэш пароля перед сохранением пользователя.

    Параметры:
        password: Новый пароль из формы создания или редактирования
            пользователя.

    Возвращает:
        Строка хэша, которую можно безопасно записать в базу данных вместо
        открытого пароля.
    """

    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Создать JWT access-token для авторизованного пользователя.

    В `data` обычно передаётся subject (`sub`) с id пользователя. Функция
    добавляет срок действия `exp`, подписывает payload секретом приложения и
    возвращает строку токена. Frontend хранит этот токен и отправляет его в
    следующих запросах к защищённым endpoint-ам.

    Параметры:
        data: Данные, которые нужно поместить в JWT. В проекте главным полем
            является `sub`.
        expires_delta: Пользовательский срок действия токена. Если не передан,
            используется ACCESS_TOKEN_EXPIRE_MINUTES из настроек.

    Возвращает:
        Подписанный JWT-токен.
    """

    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token_subject(token: str) -> int | None:
    """Извлечь id пользователя из JWT-токена.

    Функция используется и HTTP-запросами, и WebSocket-подключениями. Она
    специально возвращает None при любой ошибке токена: истёк срок действия,
    неправильная подпись, отсутствует sub или sub не преобразуется в число.
    Дальше deps/websockets превращают None в 401/закрытие соединения.

    Параметры:
        token: JWT access-token из заголовка Authorization или query-параметра.

    Возвращает:
        Id пользователя из поля `sub` или None, если токен недействителен.
    """

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            return None
        return int(sub)
    except (JWTError, ValueError, TypeError):
        return None
