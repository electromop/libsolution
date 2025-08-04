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
    print("1")
    try:
        token = request.cookies.get("access_token")
        if not token:
            print("Token not found in cookies, raising credentials_exception")  # Debugging line
            raise credentials_exception
        token = token.replace("Bearer ", "")
        print(f"Decoding token from cookies: {token}")  # Debugging line
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        print(f"Decoded email: {email}")  # Debugging line
        if email is None:
            print("Email is None, raising credentials_exception")  # Debugging line
            raise credentials_exception
    except jwt.PyJWTError as e:
        print(f"JWT Error: {e}")  # Debugging line
        raise credentials_exception
    user = get_user_by_email(email)
    if user is None:
        print("User not found, raising credentials_exception")  # Debugging line
        raise credentials_exception
    print(f"Authenticated user: {user}")  # Debugging line
    return user

def get_current_user_for_websocket(websocket: WebSocket):
    try:
        token = websocket.cookies.get("access_token")
        if not token:
            logger.debug("Token not found in cookies, raising credentials_exception")
            raise credentials_exception
        token = token.replace("Bearer ", "")
        logger.debug(f"Decoding token from cookies: {token}")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        logger.debug(f"Decoded email: {email}")
        if email is None:
            logger.debug("Email is None, raising credentials_exception")
            raise credentials_exception
    except jwt.PyJWTError as e:
        logger.debug(f"JWT Error: {e}")
        raise credentials_exception
    user = get_user_by_email(email)
    if user is None:
        logger.debug("User not found, raising credentials_exception")
        raise credentials_exception
    logger.debug(f"Authenticated user: {user}")
    return user
