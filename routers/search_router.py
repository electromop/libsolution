from fastapi import APIRouter, Depends
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, text
from auth import get_current_user
from models import SubstanceItem, get_db

router = APIRouter()

class ItemOut(BaseModel):
    id: str
    type_id: str
    data: dict
    name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Поиск по имени (работает и для PostgreSQL, и для SQLite)
@router.get("/search/name/", response_model=List[ItemOut])
def search_items_by_name(query: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    lowered_query = query.lower()
    pattern = f"%{lowered_query}%"
    # Для PostgreSQL ILIKE работает корректно для кириллицы и нечувствителен к регистру
    items = db.query(SubstanceItem).filter(
        or_(
            SubstanceItem.name.ilike(pattern),
            SubstanceItem.name.like(f"%{query}%")
        )
    ).all()
    return items

# Поиск по значениям в data (jsonb) для PostgreSQL
@router.get("/search/data/", response_model=List[ItemOut])
def search_items_by_data(query: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    Поиск по всем строковым значениям в data (jsonb).
    Для PostgreSQL используем jsonb_each_text и ILIKE.
    """
    lowered_query = query.lower()
    pattern = f"%{lowered_query}%"
    # В PostgreSQL можно пройтись по всем значениям jsonb и искать совпадения
    # Важно: используем text() для явного указания сырого SQL
    # Также важно: если substance_item.data не jsonb, а json, то надо привести к jsonb
    sql = text("""
        SELECT id FROM substance_item
        WHERE EXISTS (
            SELECT 1 FROM jsonb_each_text(substance_item.data::jsonb) AS t(key, value)
            WHERE value ILIKE :pattern
        )
    """)
    result = db.execute(sql, {"pattern": pattern})
    ids = [row[0] for row in result]
    if not ids:
        return []
    items = db.query(SubstanceItem).filter(SubstanceItem.id.in_(ids)).all()
    return items
