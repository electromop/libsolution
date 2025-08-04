# Вот как правильно разбить этот код по файлам и папкам:

# 1. Конфиг для секретов и настроек:
# substance/config.py
SECRET_KEY = "SUPER_SECRET_KEY"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# 2. JWT и авторизация:
# substance/auth/jwt_utils.py
from datetime import datetime, timedelta, timezone
import jwt
from typing import Optional
from substance.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# 3. Исключения:
# substance/auth/exceptions.py
class PermissionDenied(Exception):
    pass

# 4. Зависимости и функции авторизации:
# substance/auth/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from substance.models import User, get_db
from substance.config import SECRET_KEY, ALGORITHM
import jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Необходима авторизация",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    return user

# 5. Проверка прав:
# substance/auth/permissions.py
from sqlalchemy.orm import Session
from typing import Optional
from substance.models import User, UserPermission
from .exceptions import PermissionDenied

def check_permission(
    user: User,
    db: Session,
    entity: str,
    action: str
):
    perm: Optional[UserPermission] = (
        db.query(UserPermission)
        .filter(UserPermission.user_id == user.id, UserPermission.entity == entity)
        .first()
    )
    if not perm:
        if action == "read":
            return True
        raise PermissionDenied(f"Нет прав на {action} для {entity}")
    if action == "create" and not perm.can_create:
        raise PermissionDenied(f"Нет прав на создание {entity}")
    if action == "read" and not perm.can_read:
        raise PermissionDenied(f"Нет прав на просмотр {entity}")
    if action == "update" and not perm.can_update:
        raise PermissionDenied(f"Нет прав на изменение {entity}")
    if action == "delete" and not perm.can_delete:
        raise PermissionDenied(f"Нет прав на удаление {entity}")
    return True

def permission_required(entity: str, action: str):
    from fastapi import Depends, HTTPException, status
    from .dependencies import get_current_user
    from substance.models import get_db, User
    def dependency(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        try:
            check_permission(user, db, entity, action)
        except PermissionDenied as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        return user
    return dependency

# 6. Роуты авторизации:
# substance/auth/routes.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from substance.models import User, get_db
from .jwt_utils import create_access_token

auth_router = APIRouter()

@auth_router.post("/token")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or user.password != form_data.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверные имя пользователя или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.id})
    return {"access_token": access_token, "token_type": "bearer"}

# 7. Роуты с проверкой прав:
# substance/permission_router.py (оставить только роуты)
from fastapi import APIRouter, Depends
from substance.auth.dependencies import get_current_user
from substance.auth.permissions import permission_required
from substance.models import User

permission_router = APIRouter()

@permission_router.get("/me")
def read_users_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email
    }

@permission_router.post("/types/protected")
def create_type_protected(
    user: User = Depends(permission_required("type", "create"))
):
    return {"msg": f"Пользователь {user.username} может создавать типы."}

# ИТОГОВАЯ СТРУКТУРА ФАЙЛОВ:
# substance/
#   config.py
#   models.py
#   permission_router.py
#   auth/
#     __init__.py
#     jwt_utils.py
#     exceptions.py
#     dependencies.py
#     permissions.py
#     routes.py

# В main.py нужно будет подключить:
# from substance.auth.routes import auth_router
# from substance.permission_router import permission_router
# app.include_router(auth_router)
# app.include_router(permission_router)