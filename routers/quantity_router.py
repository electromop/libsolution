from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from uuid import uuid4

from models import SubstanceItem, SubstanceQuantityChange, get_db
from auth import get_current_user

router = APIRouter()

class QuantityChangeCreate(BaseModel):
    item_id: str
    change_type: int  # 0 - списание, 1 - пополнение
    amount: float
    reason: Optional[str] = None  # Причина списания
    created_at: Optional[datetime] = None  # Дата и время изменения количества

class QuantityChangeOut(BaseModel):
    id: str
    item_id: str
    change_type: int  # 0 - списание, 1 - пополнение
    amount: float
    reason: Optional[str] = None  # Причина списания
    created_at: Optional[datetime] = None  # Дата и время изменения количества
    user_id: Optional[str] = None

    class Config:
        from_attributes = True

@router.post("/quantity_change", response_model=QuantityChangeOut)
def change_quantity(change: QuantityChangeCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    # Проверяем, что вещество существует
    item = db.query(SubstanceItem).filter(SubstanceItem.id == change.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Вещество не найдено")
    new_change = SubstanceQuantityChange(
        id=str(uuid4()),
        item_id=change.item_id,
        change_type=change.change_type,
        amount=change.amount,
        reason=change.reason,
        created_at=change.created_at if change.created_at else datetime.utcnow(),
        user_id=None  # Можно доработать для поддержки авторизации
    )
    db.add(new_change)
    db.commit()
    db.refresh(new_change)
    return new_change

@router.get("/items/{item_id}/quantity_history", response_model=List[QuantityChangeOut])
def get_quantity_history(item_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    # История изменений количества для вещества
    changes = db.query(SubstanceQuantityChange).filter(
        SubstanceQuantityChange.item_id == item_id
    ).order_by(SubstanceQuantityChange.created_at.desc()).all()
    return changes