from passlib.context import CryptContext
import uuid
from sqlalchemy.orm import Session
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
                "hashed_password": user.hashed_password
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