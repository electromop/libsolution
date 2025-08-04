
import random
import string
import logging
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta

import requests

# Настройки Telegram-бота
TELEGRAM_BOT_TOKEN = "ВАШ_TELEGRAM_BOT_TOKEN"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# Хранилище кодов и временных связок (в реальном проекте лучше использовать Redis или БД)
telegram_2fa_codes = {}
telegram_2fa_expiry = {}
telegram_2fa_email_to_code = {}
telegram_2fa_code_to_email = {}

logger = logging.getLogger(__name__)

def generate_2fa_code(length=6):
    """Генерирует случайный цифровой код для 2FA."""
    return ''.join(random.choices(string.digits, k=length))

def get_telegram_link(code: str):
    """
    Генерирует ссылку для подтверждения через Telegram.
    Пользователь должен нажать на неё в Telegram, чтобы связать свой аккаунт.
    """
    # Предполагается, что у бота реализована обработка /start <code>
    return f"https://t.me/ВАШ_BOT_USERNAME?start={code}"

def send_telegram_code_by_link(email: str, code: str):
    """
    Информирует пользователя, что для подтверждения входа нужно перейти по ссылке в Telegram.
    """
    # В реальном проекте можно отправить email или показать ссылку на фронте
    link = get_telegram_link(code)
    logger.info(f"Пользователь {email} должен перейти по ссылке в Telegram для подтверждения: {link}")
    return link

def request_telegram_2fa(user):
    """
    Генерирует код 2FA и возвращает ссылку для подтверждения через Telegram.
    Пользователь НЕ вводит свой tg_id.
    """
    email = getattr(user, "email", None)
    if not email:
        logger.warning("У пользователя не указан email для 2FA")
        raise HTTPException(status_code=400, detail="У пользователя не найден email")
    code = generate_2fa_code()
    telegram_2fa_codes[email] = code
    telegram_2fa_expiry[email] = datetime.utcnow() + timedelta(minutes=5)
    telegram_2fa_email_to_code[email] = code
    telegram_2fa_code_to_email[code] = email
    link = send_telegram_code_by_link(email, code)
    return link

def verify_telegram_2fa(email: str):
    """
    Проверяет, прошёл ли пользователь 2FA через Telegram.
    """
    if email not in telegram_2fa_codes:
        raise HTTPException(status_code=401, detail="2FA не запрошена")
    code = telegram_2fa_codes[email]
    expiry = telegram_2fa_expiry.get(email)
    if not expiry or datetime.utcnow() > expiry:
        telegram_2fa_codes.pop(email, None)
        telegram_2fa_expiry.pop(email, None)
        telegram_2fa_email_to_code.pop(email, None)
        raise HTTPException(status_code=401, detail="Код истёк")
    # Проверка: был ли код подтверждён через Telegram-бота
    if not is_code_confirmed(code):
        raise HTTPException(status_code=401, detail="Код не подтверждён через Telegram")
    # Успешная проверка — удаляем код
    telegram_2fa_codes.pop(email, None)
    telegram_2fa_expiry.pop(email, None)
    telegram_2fa_email_to_code.pop(email, None)
    telegram_2fa_code_to_email.pop(code, None)
    return True

# --- Логика для Telegram-бота ---

# В коде самого Telegram-бота (например, на aiogram/pyTelegramBotAPI):
# Когда пользователь пишет /start <code>, бот вызывает эту функцию:
def confirm_2fa_code_from_telegram(code: str, telegram_user_id: str):
    """
    Вызывается Telegram-ботом, когда пользователь нажимает на ссылку /start <code>.
    """
    email = telegram_2fa_code_to_email.get(code)
    if not email:
        logger.warning("Код 2FA не найден или истёк")
        return False
    expiry = telegram_2fa_expiry.get(email)
    if not expiry or datetime.utcnow() > expiry:
        logger.warning("Код 2FA истёк")
        return False
    # Сохраняем факт подтверждения (можно в БД, здесь — в памяти)
    mark_code_confirmed(code)
    logger.info(f"Пользователь {email} подтвердил вход через Telegram (user_id={telegram_user_id})")
    return True

# --- Простая реализация подтверждения кода (в памяти) ---
_confirmed_codes = set()

def mark_code_confirmed(code: str):
    _confirmed_codes.add(code)

def is_code_confirmed(code: str):
    return code in _confirmed_codes

# --- Пример использования в роуте FastAPI ---
# from fastapi import APIRouter, Depends
# from substance.auth import get_current_user
#
# router = APIRouter()
#
# @router.post("/2fa/request")
# async def twofa_request(user=Depends(get_current_user)):
#     link = request_telegram_2fa(user)
#     # Можно вернуть ссылку на фронт, чтобы пользователь кликнул и подтвердил вход через Telegram
#     return JSONResponse({"detail": "Для подтверждения входа перейдите по ссылке в Telegram", "telegram_link": link})
#
# @router.post("/2fa/verify")
# async def twofa_verify(user=Depends(get_current_user)):
#     verify_telegram_2fa(user.email)
#     return JSONResponse({"detail": "2FA успешно пройдена"})
