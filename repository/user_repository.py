from passlib.context import CryptContext
import uuid
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models import SessionLocal, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_user_by_email(email: str):
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            return {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "hashed_password": user.hashed_password,
                "admin": getattr(user, "admin", False),
            }
        return None
    finally:
        db.close()

def create_user(email: str, password: str):
    db: Session = SessionLocal()
    try:
        # Проверяем, существует ли пользователь с такой почтой
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            return None
        hashed_password = pwd_context.hash(password)
        user_id = str(uuid.uuid4())
        user = User(id=user_id, email=email, hashed_password=hashed_password)
        db.add(user)
        db.commit()
        db.refresh(user)
        return {
            "id": user.id,
            "email": user.email
        }
    finally:
        db.close()

def authenticate_user(email: str, password: str):
    user = get_user_by_email(email)
    if not user:
        return None
    if not pwd_context.verify(password, user["hashed_password"]):
        return None
    return user


# --- Профиль пользователя ---

def get_user_by_id(user_id: str):
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            return {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "hashed_password": user.hashed_password,
                "created_at": user.created_at,
            }
        return None
    finally:
        db.close()


def is_email_taken(email: str, exclude_user_id: str | None = None) -> bool:
    db: Session = SessionLocal()
    try:
        query = db.query(User).filter(User.email == email)
        if exclude_user_id:
            query = query.filter(User.id != exclude_user_id)
        return db.query(query.exists()).scalar()
    finally:
        db.close()


def update_user_profile(user_id: str, email: str | None = None, username: str | None = None):
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        if email:
            # Проверяем уникальность почты
            exists = db.query(User).filter(User.email == email, User.id != user_id).first()
            if exists:
                return {"error": "EMAIL_TAKEN"}
            user.email = email
        if username is not None:
            user.username = username.strip() or None
        db.commit()
        db.refresh(user)
        return {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "created_at": user.created_at,
        }
    except IntegrityError:
        db.rollback()
        return {"error": "INTEGRITY_ERROR"}
    finally:
        db.close()


def update_user_password(user_id: str, current_password: str, new_password: str):
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"error": "NOT_FOUND"}
        if not pwd_context.verify(current_password, user.hashed_password):
            return {"error": "INVALID_PASSWORD"}
        user.hashed_password = pwd_context.hash(new_password)
        db.commit()
        return {"ok": True}
    finally:
        db.close()


# --- Админ: список пользователей ---
def list_users(limit: int = 100, offset: int = 0):
    db: Session = SessionLocal()
    try:
        query = db.query(User).order_by(User.created_at.desc())
        total = query.count()
        users = query.offset(offset).limit(limit).all()
        items = []
        for u in users:
            items.append({
                "id": u.id,
                "email": u.email,
                "username": u.username,
                "created_at": u.created_at,
                "admin": getattr(u, "admin", False),
            })
        return total, items
    finally:
        db.close()