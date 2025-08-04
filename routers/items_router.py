
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from typing import List, Optional, Literal
from pydantic import BaseModel
from sqlalchemy.orm import Session
from uuid import uuid4
from datetime import datetime
from auth import get_current_user

from models import SubstanceItem, SubstanceType, get_db

router = APIRouter(
    prefix="",
    tags=["items"],
)

# --- Jinja2 templates ---
templates = Jinja2Templates(directory="templates")
router.mount("/static", StaticFiles(directory="static"), name="static")

# --- Pydantic схемы ---
class FieldType(str):
    pass  # можно типизировать Literal["string", "int", "float", "bool", "date", "enum"]

class FieldCreate(BaseModel):
    name: str
    field_type: Literal["string", "int", "float", "bool", "date", "enum"]
    unit: Optional[str] = None
    is_required: bool = False

class TypeCreate(BaseModel):
    name: str

class TypeOut(BaseModel):
    id: str
    name: str
    fields: List[FieldCreate]

class ItemCreate(BaseModel):
    type_id: str
    name: str
    data: dict

class ItemUpdate(BaseModel):
    name: Optional[str] = None
    data: Optional[dict] = None

class ItemOut(BaseModel):
    id: str
    type_id: str
    data: dict
    name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class TypeOutWithFields(BaseModel):
    id: str
    name: str
    fields: List[FieldCreate]

    class Config:
        from_attributes = True

class ItemOutFull(BaseModel):
    id: str
    type: TypeOutWithFields
    data: dict
    name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

@router.get("/item", response_class=HTMLResponse)
def index_item(request: Request, item_id: Optional[str] = None, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if item_id:
        item_obj = db.query(SubstanceItem).filter(SubstanceItem.id == item_id).first()
        if item_obj:
            return templates.TemplateResponse("pages/index_item.html", {"request": request, "title": item_obj.name})
        else:
            return templates.TemplateResponse("pages/index_item.html", {"request": request, "title": "Вещество не найдено"})
    else:
        return templates.TemplateResponse("pages/index_item.html", {"request": request, "title": "Вещество не найдено"})

# --- API ---
@router.post("/items/", response_model=ItemOut)
def add_item(item: ItemCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    new_item = SubstanceItem(id=str(uuid4()), name=item.name, type_id=item.type_id, data=item.data)
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return ItemOut(id=new_item.id, type_id=new_item.type_id, data=new_item.data)

@router.get("/items/{item_id}", response_model=ItemOutFull)
def view_item_json(item_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    Возвращает всю информацию о веществе (item) в формате JSON, включая поля типа (вложенно).
    """
    item = db.query(SubstanceItem).filter(SubstanceItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    type_obj = db.query(SubstanceType).filter(SubstanceType.id == item.type_id).first()
    if not type_obj:
        raise HTTPException(status_code=404, detail="Type not found")
    # Получаем все поля типа
    fields = [FieldCreate(
        name=f.name, field_type=f.field_type, unit=f.unit, is_required=f.is_required
    ) for f in type_obj.fields]
    type_out = TypeOutWithFields(
        id=type_obj.id,
        name=type_obj.name,
        fields=fields
    )
    return ItemOutFull(
        id=item.id,
        type=type_out,
        data=item.data,
        name=item.name,
        created_at=item.created_at,
        updated_at=item.updated_at
    )

@router.get("/items/", response_model=List[ItemOut])
def list_items(type_id: Optional[str] = None, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    query = db.query(SubstanceItem)
    if type_id:
        query = query.filter(SubstanceItem.type_id == type_id)
    return query.all()

# --- Новый эндпоинт для редактирования item ---
@router.put("/items/{item_id}", response_model=ItemOut)
def update_item(item_id: str, item_update: ItemUpdate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    item = db.query(SubstanceItem).filter(SubstanceItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Вещество не найдено")
    if item_update.name is not None:
        item.name = item_update.name
    if item_update.data is not None:
        item.data = item_update.data
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return item

# --- Новый эндпоинт для удаления item ---
@router.delete("/items/{item_id}")
def delete_item(item_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    item = db.query(SubstanceItem).filter(SubstanceItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Вещество не найдено")
    db.delete(item)
    db.commit()
    return {"status": "ok", "message": "Вещество удалено"}
