import jwt
import logging
from datetime import datetime, timedelta, UTC
from fastapi import HTTPException, status, Depends, Request, WebSocket
from repository.user_repository import get_user_by_email
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

SECRET_KEY = "your_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Не удалось проверить учетные данные",
    headers={"WWW-Authenticate": "Bearer"},
)

# def credentials_exception():
#     return RedirectResponse(url="/login", status_code=302)

response_login = RedirectResponse(url="/login", status_code=302)

def create_access_token(data: dict, expires_delta: timedelta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)):
    to_encode = data.copy()
    expire = datetime.now(UTC) + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(request: Request):
    try:
        token = request.cookies.get("access_token")
        if not token:
            print("Token not found in cookies, raising credentials_exception")  # Debugging line
            raise credentials_exception
        token = token.replace("Bearer ", "")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except jwt.PyJWTError as e:
        raise credentials_exception
    user = get_user_by_email(email)
    if user is None:
        raise credentials_exception
    return user

def get_current_user_for_websocket(websocket: WebSocket):
    try:
        token = websocket.cookies.get("access_token")
        if not token:
            logger.debug("Token not found in cookies, raising credentials_exception")
            raise credentials_exception
        token = token.replace("Bearer ", "")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except jwt.PyJWTError as e:
        raise credentials_exception
    user = get_user_by_email(email)
    if user is None:
        raise credentials_exception
    return user
