"""API управления учётными записями пользователей системы.

Этот router используется супер-администратором для создания и изменения
пользователей, которые входят в веб-приложение: оператор КПП, техник, HR,
аналитик и другой администратор. Важно понимать различие между сотрудником и
пользователем: сотрудник описывает человека как объект кадрового учёта, а
пользователь описывает его право входить в систему и выполнять действия в
рамках роли.

Модуль не занимается регистрацией через публичную форму. Это административное
управление доступом: кто может войти, какая роль назначена и привязана ли
учётная запись к карточке сотрудника.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, SQLModel, select

from app.core.database import get_session
from app.core.deps import get_current_user, require_permissions
from app.core.permissions import USERS_MANAGE
from app.core.security import get_password_hash
from app.models.employees import Employee
from app.models.user import User, UserRole

router = APIRouter(prefix="/api/users", tags=["Пользователи"])

ASSIGNABLE_ROLES = {
    UserRole.SUPER_ADMIN,
    UserRole.CHECKPOINT_OPERATOR,
    UserRole.TECHNICIAN,
    UserRole.HR,
    UserRole.ANALYST,
}


class UserRead(SQLModel):
    """DTO пользователя, который можно безопасно вернуть frontend-у.

    Пароль и password_hash никогда не включаются в ответ. Интерфейсу нужны
    только id, логин, роль, активность и имя привязанного сотрудника, чтобы
    администратор понимал, кому принадлежит учётная запись.
    """

    id: int
    username: str
    role: UserRole
    is_active: bool
    employee_id: int | None = None
    employee_name: str | None = None


class UserCreate(SQLModel):
    """Данные для создания новой учётной записи.

    Payload приходит из административной формы. Пароль передаётся только один
    раз, сразу хэшируется и в открытом виде в базе не хранится. Роль ограничена
    списком ASSIGNABLE_ROLES, чтобы через API нельзя было назначить внутреннее
    или несуществующее значение.
    """

    username: str
    password: str
    role: UserRole = UserRole.CHECKPOINT_OPERATOR
    is_active: bool = True
    employee_id: int | None = None


class UserUpdate(SQLModel):
    """Данные частичного изменения пользователя.

    Все поля необязательные, потому что форма редактирования может менять только
    логин, только роль, только активность или только пароль. Endpoint применяет
    только переданные поля и отдельно проверяет каждое изменение.
    """

    username: str | None = None
    password: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    employee_id: int | None = None


def build_employee_name(employee: Employee | None) -> str | None:
    """Собрать отображаемое ФИО сотрудника для карточки пользователя.

    Параметры:
        employee: Модель сотрудника, привязанная к учётной записи, или None,
            если пользователь является технической/административной записью без
            кадровой карточки.

    Возвращает:
        Строка ФИО без лишних пробелов или None, если сотрудник не передан.
    """

    if not employee:
        return None
    return " ".join(
        part for part in [employee.last_name, employee.first_name, employee.middle_name] if part
    ).strip() or None


def build_user_read(session: Session, user: User) -> UserRead:
    """Преобразовать модель User в DTO для списка пользователей.

    Функция дополнительно подгружает сотрудника по employee_id, потому что
    frontend должен показывать не только числовой идентификатор, но и понятное
    имя человека. Это небольшая сборка view-model поверх данных БД.

    Параметры:
        session: Сессия БД для чтения связанного сотрудника.
        user: Учётная запись, которую нужно показать в интерфейсе.

    Возвращает:
        UserRead без чувствительных данных.
    """

    employee = session.get(Employee, user.employee_id) if user.employee_id else None
    return UserRead(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        employee_id=user.employee_id,
        employee_name=build_employee_name(employee),
    )


def validate_employee_link(session: Session, employee_id: int | None, ignore_user_id: int | None = None) -> None:
    """Проверить, можно ли привязать сотрудника к учётной записи.

    Один сотрудник не должен иметь несколько логинов, иначе в системе станет
    непонятно, какие действия выполнял конкретный человек. При редактировании
    текущего пользователя его собственная привязка игнорируется, чтобы форма
    могла сохраняться без ложной ошибки.

    Параметры:
        session: Сессия БД для поиска сотрудника и существующей привязки.
        employee_id: Идентификатор сотрудника из формы или None, если
            пользователь не привязывается к сотруднику.
        ignore_user_id: Id пользователя, которого сейчас редактируют. Нужен,
            чтобы не считать его же текущую связь конфликтом.

    Ошибки:
        HTTPException: 400, если сотрудник не найден или уже привязан к другой
        учётной записи.
    """

    if employee_id is None:
        return

    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=400, detail="Указанный сотрудник не найден")

    existing_user = session.exec(select(User).where(User.employee_id == employee_id)).first()
    if existing_user and existing_user.id != ignore_user_id:
        raise HTTPException(status_code=400, detail="Этот сотрудник уже привязан к другому пользователю")


def validate_assignable_role(role: UserRole) -> None:
    """Проверить, что роль можно назначить через административный интерфейс.

    Даже если enum содержит только известные роли, эта проверка оставлена как
    явный уровень защиты бизнес-правила: администратор может назначать только
    роли из ASSIGNABLE_ROLES. Если позже появится служебная роль, её не получится
    случайно выдать обычному пользователю.

    Параметры:
        role: Роль, выбранная в форме пользователя.

    Ошибки:
        HTTPException: 400, если роль не входит в список доступных для
        назначения.
    """

    if role not in ASSIGNABLE_ROLES:
        raise HTTPException(
            status_code=400,
            detail="Эта роль недоступна для назначения",
        )


@router.get(
    "/",
    response_model=List[UserRead],
    dependencies=[Depends(require_permissions(USERS_MANAGE))],
)
def get_users(session: Session = Depends(get_session)):
    """Получить список учётных записей для административной страницы.

    Endpoint доступен только пользователю с правом USERS_MANAGE. Список
    сортируется по убыванию id, чтобы новые записи были сверху.

    Параметры:
        session: Сессия БД.

    Возвращает:
        Список пользователей без password_hash.
    """

    users = session.exec(select(User).order_by(User.id.desc())).all()
    return [build_user_read(session, user) for user in users]


@router.post(
    "/",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(USERS_MANAGE))],
)
def create_user(payload: UserCreate, session: Session = Depends(get_session)):
    """Создать новую учётную запись пользователя.

    Функция выполняет все проверки, которые важны для безопасного доступа:
    минимальная длина логина и пароля, уникальность логина, допустимость роли и
    корректность привязки к сотруднику. Пароль сразу превращается в хэш через
    security-сервис, поэтому открытый пароль не сохраняется.

    Параметры:
        payload: Данные формы создания пользователя.
        session: Сессия БД, в которой создаётся User.

    Возвращает:
        Созданный пользователь в формате UserRead.

    Ошибки:
        HTTPException: 400 при ошибках валидации формы, конфликте логина,
        недопустимой роли или невозможной привязке сотрудника.
    """

    username = payload.username.strip()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Логин должен содержать минимум 3 символа")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Пароль должен содержать минимум 6 символов")

    validate_assignable_role(payload.role)

    exists = session.exec(select(User).where(User.username == username)).first()
    if exists:
        raise HTTPException(status_code=400, detail="Пользователь с таким логином уже существует")

    validate_employee_link(session, payload.employee_id)

    user = User(
        username=username,
        password_hash=get_password_hash(payload.password),
        role=payload.role,
        is_active=payload.is_active,
        employee_id=payload.employee_id,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return build_user_read(session, user)


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    dependencies=[Depends(require_permissions(USERS_MANAGE))],
)
def update_user(
    user_id: int,
    payload: UserUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Изменить существующую учётную запись пользователя.

    Endpoint работает как PATCH: меняются только поля, которые пришли в payload.
    Для каждого поля выполняется отдельная проверка. Особо защищены две ситуации:
    администратор не может снять роль super_admin у самого себя и не может
    деактивировать собственную учётную запись. Иначе можно случайно потерять
    доступ к управлению системой.

    Параметры:
        user_id: Идентификатор редактируемого пользователя.
        payload: Частичный набор изменений.
        session: Сессия БД.
        current_user: Пользователь, выполняющий изменение. Он нужен для защиты
            от самоотключения администратора.

    Возвращает:
        Обновлённый пользователь в формате UserRead.

    Ошибки:
        HTTPException: 404, если пользователь не найден; 400 при ошибках
        валидации, конфликте логина, недопустимой роли, конфликте сотрудника или
        попытке администратора лишить доступа самого себя.
    """

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    data = payload.model_dump(exclude_unset=True)

    if "username" in data:
        username = (data["username"] or "").strip()
        if len(username) < 3:
            raise HTTPException(status_code=400, detail="Логин должен содержать минимум 3 символа")
        exists = session.exec(select(User).where(User.username == username, User.id != user_id)).first()
        if exists:
            raise HTTPException(status_code=400, detail="Пользователь с таким логином уже существует")
        user.username = username

    if "employee_id" in data:
        validate_employee_link(session, data["employee_id"], ignore_user_id=user_id)
        user.employee_id = data["employee_id"]

    if "role" in data:
        validate_assignable_role(data["role"])
        if current_user.id == user.id and data["role"] != UserRole.SUPER_ADMIN:
            raise HTTPException(status_code=400, detail="Нельзя снять роль super_admin у своей учетной записи")
        user.role = data["role"]

    if "is_active" in data:
        if current_user.id == user.id and data["is_active"] is False:
            raise HTTPException(status_code=400, detail="Нельзя деактивировать свою учетную запись")
        user.is_active = data["is_active"]

    if "password" in data and data["password"]:
        if len(data["password"]) < 6:
            raise HTTPException(status_code=400, detail="Пароль должен содержать минимум 6 символов")
        user.password_hash = get_password_hash(data["password"])

    session.add(user)
    session.commit()
    session.refresh(user)
    return build_user_read(session, user)
