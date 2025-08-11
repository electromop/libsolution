from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from typing import List, Optional, Literal
from uuid import uuid4

from pydantic import BaseModel
from models import SubstanceType, SubstanceField, get_db
from sqlalchemy.orm import Session
from sqlalchemy import text

from auth import get_current_user
from repository.audit_repository import write_audit_log

router = APIRouter()

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

class FieldOut(FieldCreate):
    id: str

class FieldUpdate(BaseModel):
    name: Optional[str] = None
    field_type: Optional[Literal["string", "int", "float", "bool", "date", "enum"]] = None
    unit: Optional[str] = None
    is_required: Optional[bool] = None

class TypeCreate(BaseModel):
    name: str

class TypeOut(BaseModel):
    id: str
    name: str
    fields: List[FieldOut]

# --- Эндпоинт для страницы index.html ---

@router.get("/substance", response_class=HTMLResponse)
def index_substance(request: Request, type_id: Optional[str] = None, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if type_id:
        type_obj = db.query(SubstanceType).filter(SubstanceType.id == type_id).first()
        if type_obj:
            return templates.TemplateResponse("pages/index.html", {"request": request, "title": type_obj.name})
        else:
            return templates.TemplateResponse("pages/index.html", {"request": request, "title": "Вещества"})
    else:
        return templates.TemplateResponse("pages/index.html", {"request": request, "title": "Вещества"})
    
@router.get("/", response_class=HTMLResponse)
def index_index_substance(request: Request, type_id: Optional[str] = None, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if type_id:
        type_obj = db.query(SubstanceType).filter(SubstanceType.id == type_id).first()
        if type_obj:
            return templates.TemplateResponse("pages/index.html", {"request": request, "title": type_obj.name})
        else:
            return templates.TemplateResponse("pages/index.html", {"request": request, "title": "Вещества"})
    else:
        return templates.TemplateResponse("pages/index.html", {"request": request, "title": "Вещества"})


@router.post("/types/", response_model=TypeOut)
def create_type(payload: TypeCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    type_id = str(uuid4())
    new_type = SubstanceType(id=type_id, name=payload.name)
    db.add(new_type)
    db.commit()
    db.refresh(new_type)
    # аудит: добавление типа
    write_audit_log(
        method="POST",
        path=f"/types/",
        user_id=current_user.get("id"),
        email=current_user.get("email"),
        action="CREATE_TYPE",
        entity="substance_type",
        entity_id=new_type.id,
        details={"name": new_type.name},
    )
    return TypeOut(id=new_type.id, name=new_type.name, fields=[])

@router.get("/types/", response_model=List[TypeOut])
def list_types(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    types = db.query(SubstanceType).all()
    result = []
    for t in types:
        fields = [FieldOut(
            id=f.id, name=f.name, field_type=f.field_type, unit=f.unit, is_required=f.is_required
        ) for f in t.fields]
        result.append(TypeOut(id=t.id, name=t.name, fields=fields))
    return result

@router.get("/types/{type_id}/fields", response_model=List[FieldOut])
def get_fields_by_type_id(type_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    type_instance = db.query(SubstanceType).filter(SubstanceType.id == type_id).first()
    if not type_instance:
        raise HTTPException(status_code=404, detail="Type not found")
    fields = [FieldOut(
        id=f.id, name=f.name, field_type=f.field_type, unit=f.unit, is_required=f.is_required
    ) for f in type_instance.fields]
    return fields

@router.post("/types/{type_id}/fields")
def add_field(type_id: str, field: FieldCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    f = SubstanceField(
        id=str(uuid4()), name=field.name, field_type=field.field_type,
        unit=field.unit, is_required=field.is_required, type_id=type_id
    )
    db.add(f)
    db.commit()
    # аудит: добавление поля типа
    write_audit_log(
        method="POST",
        path=f"/types/{type_id}/fields",
        user_id=current_user.get("id"),
        email=current_user.get("email"),
        action="ADD_FIELD",
        entity="substance_field",
        entity_id=f.id,
        details={"type_id": type_id, "name": f.name},
    )
    return {"status": "ok"}

@router.put("/types/{type_id}/fields/{field_id}", response_model=FieldOut)
def update_field(type_id: str, field_id: str, payload: FieldUpdate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    field = db.query(SubstanceField).filter(SubstanceField.id == field_id, SubstanceField.type_id == type_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    old_name = field.name
    if payload.name is not None:
        field.name = payload.name
    if payload.field_type is not None:
        field.field_type = payload.field_type
    if payload.unit is not None:
        field.unit = payload.unit
    if payload.is_required is not None:
        field.is_required = payload.is_required
    db.commit()
    db.refresh(field)
    # Если изменилось имя поля — синхронизируем ключи в JSONB у всех элементов данного типа
    if payload.name is not None and payload.name != old_name:
        try:
            sql = text(
                """
                UPDATE substance_item
                SET data = (
                    jsonb_set(
                        (data::jsonb) - :old_key,
                        ( '{' || :new_key || '}' )::text[],
                        (data::jsonb)->:old_key,
                        true
                    )
                )::json
                WHERE type_id = :type_id AND (data::jsonb ? :old_key);
                """
            )
            db.execute(sql, {"old_key": old_name, "new_key": payload.name, "type_id": type_id})
            db.commit()
        except Exception:
            # В случае ошибки синхронизации не падаем на обновлении поля
            pass
    # аудит: изменение поля
    write_audit_log(
        method="PUT",
        path=f"/types/{type_id}/fields/{field_id}",
        user_id=current_user.get("id"),
        email=current_user.get("email"),
        action="UPDATE_FIELD",
        entity="substance_field",
        entity_id=field.id,
        details={
            "type_id": type_id,
            "changes": {
                k: v for k, v in payload.model_dump(exclude_none=True).items()
            }
        },
    )
    return FieldOut(id=field.id, name=field.name, field_type=field.field_type, unit=field.unit, is_required=field.is_required)

@router.delete("/types/{type_id}/fields/{field_id}")
def delete_field(type_id: str, field_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    field = db.query(SubstanceField).filter(SubstanceField.id == field_id, SubstanceField.type_id == type_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    db.delete(field)
    db.commit()
    # аудит: удаление поля
    write_audit_log(
        method="DELETE",
        path=f"/types/{type_id}/fields/{field_id}",
        user_id=current_user.get("id"),
        email=current_user.get("email"),
        action="DELETE_FIELD",
        entity="substance_field",
        entity_id=field_id,
        details={"type_id": type_id},
    )
    return {"status": "ok"}