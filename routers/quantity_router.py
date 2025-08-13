from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
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
    user_email: Optional[str] = None

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
        user_id=current_user["id"]
    )
    db.add(new_change)
    db.commit()
    db.refresh(new_change)
    return {
        "id": new_change.id,
        "item_id": new_change.item_id,
        "change_type": int(new_change.change_type),
        "amount": new_change.amount,
        "reason": new_change.reason,
        "created_at": new_change.created_at,
        "user_id": current_user["id"],
        "user_email": current_user.get("email")
    }

@router.get("/items/{item_id}/quantity_history", response_model=List[QuantityChangeOut])
def get_quantity_history(item_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    # История изменений количества для вещества
    changes = db.query(SubstanceQuantityChange).filter(
        SubstanceQuantityChange.item_id == item_id
    ).order_by(SubstanceQuantityChange.created_at.desc()).all()
    result = []
    for ch in changes:
        result.append({
            "id": ch.id,
            "item_id": ch.item_id,
            "change_type": int(ch.change_type),
            "amount": ch.amount,
            "reason": ch.reason,
            "created_at": ch.created_at,
            "user_id": ch.user_id,
            "user_email": getattr(ch.user, "email", None) if ch.user else None
        })
    return result

@router.get("/items/{item_id}/quantity")
def get_current_quantity(item_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    # Текущее количество = сумма пополнений - сумма списаний
    added = db.query(func.coalesce(func.sum(SubstanceQuantityChange.amount), 0.0)).filter(
        SubstanceQuantityChange.item_id == item_id,
        SubstanceQuantityChange.change_type == True
    ).scalar() or 0.0
    removed = db.query(func.coalesce(func.sum(SubstanceQuantityChange.amount), 0.0)).filter(
        SubstanceQuantityChange.item_id == item_id,
        SubstanceQuantityChange.change_type == False
    ).scalar() or 0.0
    quantity = float(added) - float(removed)
    return {"quantity": quantity}