
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from sqlalchemy.orm import Session

# Импорт моделей и зависимости для получения сессии БД
from models import SubstanceTag, SubstanceItemTag
from models import get_db
from auth import get_current_user

router = APIRouter(
    prefix="",
    tags=["tags"],
)

# Работа с ТЕГАМИ

class TagCreate(BaseModel):
    name: str

class TagOut(BaseModel):
    id: str
    name: str

    class Config:
        from_attributes = True

@router.post("/tags/", response_model=TagOut)
def create_tag(tag: TagCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    from uuid import uuid4
    # Проверяем, что такого тега нет
    existing = db.query(SubstanceTag).filter(SubstanceTag.name == tag.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Тег с таким именем уже существует")
    new_tag = SubstanceTag(id=str(uuid4()), name=tag.name)
    db.add(new_tag)
    db.commit()
    db.refresh(new_tag)
    return new_tag

@router.get("/tags/", response_model=List[TagOut])
def list_tags(db: Session = Depends(get_db)):
    tags = db.query(SubstanceTag).all()
    return tags

# Привязка тегов к веществу

class ItemTagOut(BaseModel):
    id: str
    item_id: str
    tag_id: str

    class Config:
        from_attributes = True

@router.post("/items/{item_id}/tags/{tag_id}", response_model=ItemTagOut)
def add_tag_to_item(item_id: str, tag_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    from uuid import uuid4
    # Проверяем, что такой связи ещё нет
    existing = db.query(SubstanceItemTag).filter(
        SubstanceItemTag.item_id == item_id,
        SubstanceItemTag.tag_id == tag_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Тег уже привязан к веществу")
    new_item_tag = SubstanceItemTag(id=str(uuid4()), item_id=item_id, tag_id=tag_id)
    db.add(new_item_tag)
    db.commit()
    db.refresh(new_item_tag)
    return new_item_tag

@router.delete("/items/{item_id}/tags/{tag_id}")
def remove_tag_from_item(item_id: str, tag_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    item_tag = db.query(SubstanceItemTag).filter(
        SubstanceItemTag.item_id == item_id,
        SubstanceItemTag.tag_id == tag_id
    ).first()
    if not item_tag:
        raise HTTPException(status_code=404, detail="Связь не найдена")
    db.delete(item_tag)
    db.commit()
    return {"status": "ok", "message": "Тег отвязан от вещества"}

@router.get("/items/{item_id}/tags", response_model=List[TagOut])
def get_tags_for_item(item_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    tags = db.query(SubstanceTag).join(SubstanceItemTag, SubstanceTag.id == SubstanceItemTag.tag_id).filter(
        SubstanceItemTag.item_id == item_id
    ).all()
    return tags
