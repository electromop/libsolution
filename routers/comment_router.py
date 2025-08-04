# Работа с комментариями к веществу

from fastapi import APIRouter, Depends
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy.orm import Session, joinedload

# Импорт моделей и зависимостей из основного приложения
from models import SubstanceItemComment, get_db, User  # Предполагаем, что есть модель User
from auth import get_current_user

router = APIRouter()

class UserInfo(BaseModel):
    id: str
    username: Optional[str] = None
    email: Optional[str] = None

    class Config:
        from_attributes = True

class ItemCommentCreate(BaseModel):
    user_id: Optional[str] = None
    text: str

class ItemCommentOut(BaseModel):
    id: str
    item_id: str
    user_id: Optional[str] = None
    text: str
    created_at: datetime
    user: Optional[UserInfo] = None  # Информация о пользователе

    class Config:
        from_attributes = True

@router.post("/items/{item_id}/comments", response_model=ItemCommentOut)
def add_item_comment(
    item_id: str,
    comment: ItemCommentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    from uuid import uuid4
    new_comment = SubstanceItemComment(
        id=str(uuid4()),
        item_id=item_id,
        user_id=current_user['id'],
        text=comment.text
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    # Загружаем пользователя через ORM связь, если она определена
    db.refresh(new_comment)
    return new_comment

@router.get("/items/{item_id}/comments", response_model=List[ItemCommentOut])
def get_item_comments(
    item_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Используем joinedload для подгрузки пользователя через ORM
    comments = db.query(SubstanceItemComment).options(joinedload(SubstanceItemComment.user)).filter(
        SubstanceItemComment.item_id == item_id
    ).order_by(SubstanceItemComment.created_at.desc()).all()
    return comments