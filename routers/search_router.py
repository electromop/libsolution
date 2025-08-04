from fastapi import APIRouter, Depends
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from auth import get_current_user
# Импорт моделей и зависимостей из основного приложения
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

# В SQLite функция lower не всегда корректно работает с кириллицей, если не подключено расширение ICU.
# Поэтому для поиска по кириллице делаем двойную проверку: обычный LIKE и lower+LIKE.
# Это увеличивает шанс найти "Бензол" по запросу "бен" или "БЕН".
@router.get("/search/name/", response_model=List[ItemOut])
def search_items_by_name(query: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    lowered_query = query.lower()
    pattern = f"%{lowered_query}%"
    # Делаем OR: либо совпадение с lower(name), либо с обычным name (на случай, если lower не работает с кириллицей)
    items = db.query(SubstanceItem).filter(
        func.lower(SubstanceItem.name).like(pattern) | SubstanceItem.name.like(f"%{query}%")
    ).all()
    return items

@router.get("/search/data/", response_model=List[ItemOut])
def search_items_by_data(query: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    # Поиск по всем строковым значениям в data (SQLite: json_each)
    # Используем сырой SQL, чтобы получить id подходящих записей
    lowered_query = query.lower()
    pattern = f"%{lowered_query}%"
    sql = text("""
        SELECT id FROM substance_item
        WHERE EXISTS (
            SELECT 1 FROM json_each(substance_item.data)
            WHERE typeof(json_each.value) = 'text'
              AND lower(json_each.value) LIKE :pattern
        )
    """)
    result = db.execute(sql, {"pattern": pattern})
    ids = [row[0] for row in result]  # row[0], а не row["id"], т.к. возвращается tuple
    if not ids:
        return []
    items = db.query(SubstanceItem).filter(SubstanceItem.id.in_(ids)).all()
    return items