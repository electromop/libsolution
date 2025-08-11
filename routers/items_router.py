
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from typing import List, Optional, Literal
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, cast, func
from sqlalchemy.types import Float as SAFloat, Integer as SAInteger, String as SAString
from uuid import uuid4
from datetime import datetime, UTC
from auth import get_current_user
from repository.audit_repository import write_audit_log

from models import SubstanceItem, SubstanceType, SubstanceField, get_db

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

# --- Фильтрация ---
class ItemsFilterRequest(BaseModel):
    type_id: str
    filters: dict

def _apply_base_filters(query, filters):
    # Фильтр по названию
    name = filters.get("name")
    name_mode = filters.get("name_mode")
    if name:
        pattern = f"%{name}%"
        if name_mode == "equals":
            query = query.filter(SubstanceItem.name == name)
        else:
            query = query.filter(SubstanceItem.name.ilike(pattern))

    # Фильтр по дате создания (created_at)
    date_from = filters.get("date_from")
    date_to = filters.get("date_to")
    if date_from:
        try:
            dt_from = datetime.fromisoformat(str(date_from)).replace(tzinfo=UTC) if len(str(date_from)) == 10 else datetime.fromisoformat(str(date_from))
            query = query.filter(SubstanceItem.created_at >= dt_from)
        except Exception:
            pass
    if date_to:
        try:
            # включительно конец дня
            if len(str(date_to)) == 10:
                dt_to = datetime.fromisoformat(str(date_to) + "T23:59:59").replace(tzinfo=UTC)
            else:
                dt_to = datetime.fromisoformat(str(date_to))
            query = query.filter(SubstanceItem.created_at <= dt_to)
        except Exception:
            pass
    return query

def _apply_dynamic_field_filters(query, filters, type_fields):
    # Перебираем известные поля типа и применяем согласно их типу
    for f in type_fields:
        field_name = f.name
        field_id = getattr(f, 'id', None)
        # Извлекаем текст по id или по имени: COALESCE(data->>id, data->>name)
        json_text_candidates = []
        if field_id:
            json_text_candidates.append(SubstanceItem.data.op('->>')(field_id))
        json_text_candidates.append(SubstanceItem.data.op('->>')(field_name))
        json_text = func.coalesce(*json_text_candidates)
        if f.field_type in ("string", "enum"):
            mode = filters.get(f"field_{field_id}_mode") if field_id and f"field_{field_id}_mode" in filters else filters.get(f"field_{field_name}_mode")
            value = filters.get(f"field_{field_id}") if field_id and f"field_{field_id}" in filters else filters.get(f"field_{field_name}")
            if value is None or value == "":
                continue
            if mode == "equals":
                query = query.filter(json_text == value)
            elif mode == "not_equals":
                query = query.filter(json_text != value)
            else:
                query = query.filter(json_text.ilike(f"%{value}%"))
        elif f.field_type in ("int", "float"):
            v_from = filters.get(f"field_{field_id}_from") if field_id and f"field_{field_id}_from" in filters else filters.get(f"field_{field_name}_from")
            v_to = filters.get(f"field_{field_id}_to") if field_id and f"field_{field_id}_to" in filters else filters.get(f"field_{field_name}_to")
            if v_from is None and v_to is None:
                continue
            cast_type = SAFloat if f.field_type == "float" else SAInteger
            json_num = cast(json_text, cast_type)
            if v_from not in (None, ""):
                try:
                    v_from_cast = float(v_from) if f.field_type == "float" else int(v_from)
                    query = query.filter(json_num >= v_from_cast)
                except Exception:
                    pass
            if v_to not in (None, ""):
                try:
                    v_to_cast = float(v_to) if f.field_type == "float" else int(v_to)
                    query = query.filter(json_num <= v_to_cast)
                except Exception:
                    pass
        elif f.field_type == "bool":
            # ожидаем значение one of ["any", "true", "false"]
            val = filters.get(f"field_{field_id}") if field_id and f"field_{field_id}" in filters else filters.get(f"field_{field_name}")
            if val in (None, "", "any"):
                continue
            if isinstance(val, bool):
                desired = val
            else:
                desired = True if str(val).lower() == "true" else False
            query = query.filter(
                func.lower(json_text).in_(["true", "1"]) if desired else func.lower(json_text).in_(["false", "0"])
            )
        elif f.field_type == "date":
            d_from = filters.get(f"field_{field_id}_from") if field_id and f"field_{field_id}_from" in filters else filters.get(f"field_{field_name}_from")
            d_to = filters.get(f"field_{field_id}_to") if field_id and f"field_{field_id}_to" in filters else filters.get(f"field_{field_name}_to")
            if not d_from and not d_to:
                continue
            # сравнение по строке в формате YYYY-MM-DD корректно лексикографически
            if d_from:
                query = query.filter(json_text >= d_from)
            if d_to:
                query = query.filter(json_text <= d_to)
        else:
            # неизвестный тип — пропускаем
            continue
    return query

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
    # аудит: добавление вещества
    write_audit_log(
        method="POST",
        path="/items/",
        user_id=current_user.get("id"),
        email=current_user.get("email"),
        action="ADD_ITEM",
        entity="substance_item",
        entity_id=new_item.id,
        details={"type_id": new_item.type_id, "name": new_item.name},
    )
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
    before = {"name": item.name, "data": item.data}
    if item_update.name is not None:
        item.name = item_update.name
    if item_update.data is not None:
        item.data = item_update.data
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    # аудит: изменение вещества
    changes = {}
    if item_update.name is not None and item_update.name != before["name"]:
        changes["name"] = item_update.name
    if item_update.data is not None and item_update.data != before["data"]:
        changes["data"] = "updated"
    if changes:
        write_audit_log(
            method="PUT",
            path=f"/items/{item_id}",
            user_id=current_user.get("id"),
            email=current_user.get("email"),
            action="UPDATE_ITEM",
            entity="substance_item",
            entity_id=item.id,
            details={"changes": changes},
        )
    return item

@router.post("/items/filter", response_model=List[ItemOut])
def filter_items(payload: ItemsFilterRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    # Проверяем тип и получаем его поля
    type_obj = db.query(SubstanceType).filter(SubstanceType.id == payload.type_id).first()
    if not type_obj:
        raise HTTPException(status_code=404, detail="Тип не найден")
    # Берём ORM-поля, чтобы иметь доступ к id и name
    orm_fields = type_obj.fields

    query = db.query(SubstanceItem).filter(SubstanceItem.type_id == payload.type_id)
    query = _apply_base_filters(query, payload.filters or {})
    query = _apply_dynamic_field_filters(query, payload.filters or {}, orm_fields)
    items = query.all()
    return items

# --- Новый эндпоинт для удаления item ---
@router.delete("/items/{item_id}")
def delete_item(item_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    item = db.query(SubstanceItem).filter(SubstanceItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Вещество не найдено")
    # аудит до удаления, чтобы иметь id/name
    write_audit_log(
        method="DELETE",
        path=f"/items/{item_id}",
        user_id=current_user.get("id"),
        email=current_user.get("email"),
        action="DELETE_ITEM",
        entity="substance_item",
        entity_id=item_id,
        details={"name": item.name},
    )
    db.delete(item)
    db.commit()
    return {"status": "ok", "message": "Вещество удалено"}
