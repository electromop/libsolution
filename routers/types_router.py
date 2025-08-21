from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from typing import List, Optional, Literal
from uuid import uuid4

from pydantic import BaseModel
from models import (
    SubstanceType,
    SubstanceField,
    SubstanceUnit,
    SubstanceItem,
    SubstanceQuantityChange,
    SubstanceItemComment,
    SubstanceItemTag,
    get_db,
)
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
    # список единиц измерения
    units: List[dict] | None = None

class TypeUpdate(BaseModel):
    name: Optional[str] = None

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
    # Создаём базовую единицу измерения по умолчанию (1.0)
    base_unit = SubstanceUnit(id=str(uuid4()), type_id=new_type.id, name="ед.", ratio_to_base=1.0, is_default=True)
    db.add(base_unit)
    db.commit()
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
    return TypeOut(id=new_type.id, name=new_type.name, fields=[], units=[{"id": base_unit.id, "name": base_unit.name, "ratio_to_base": base_unit.ratio_to_base, "is_default": base_unit.is_default}])

@router.get("/types/", response_model=List[TypeOut])
def list_types(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    types = db.query(SubstanceType).all()
    result = []
    for t in types:
        fields = [FieldOut(
            id=f.id, name=f.name, field_type=f.field_type, unit=f.unit, is_required=f.is_required
        ) for f in t.fields]
        # грузим единицы
        units = db.query(SubstanceUnit).filter(SubstanceUnit.type_id == t.id).all()
        result.append(TypeOut(
            id=t.id,
            name=t.name,
            fields=fields,
            units=[{"id": u.id, "name": u.name, "ratio_to_base": u.ratio_to_base, "is_default": u.is_default} for u in units]
        ))
    return result

@router.put("/types/{type_id}", response_model=TypeOut)
def update_type(type_id: str, payload: TypeUpdate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    type_obj = db.query(SubstanceType).filter(SubstanceType.id == type_id).first()
    if not type_obj:
        raise HTTPException(status_code=404, detail="Type not found")
    if payload.name is not None:
        type_obj.name = payload.name
    db.commit()
    db.refresh(type_obj)
    # собрать поля и единицы для ответа
    fields = [FieldOut(id=f.id, name=f.name, field_type=f.field_type, unit=f.unit, is_required=f.is_required) for f in type_obj.fields]
    units = db.query(SubstanceUnit).filter(SubstanceUnit.type_id == type_obj.id).all()
    # аудит: изменение типа
    write_audit_log(
        method="PUT",
        path=f"/types/{type_id}",
        user_id=current_user.get("id"),
        email=current_user.get("email"),
        action="UPDATE_TYPE",
        entity="substance_type",
        entity_id=type_obj.id,
        details={"changes": payload.model_dump(exclude_none=True)},
    )
    return TypeOut(
        id=type_obj.id,
        name=type_obj.name,
        fields=fields,
        units=[{"id": u.id, "name": u.name, "ratio_to_base": u.ratio_to_base, "is_default": u.is_default} for u in units]
    )

@router.delete("/types/{type_id}")
def delete_type(type_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    type_obj = db.query(SubstanceType).filter(SubstanceType.id == type_id).first()
    if not type_obj:
        raise HTTPException(status_code=404, detail="Type not found")
    # Удаляем зависимые сущности вручную
    # 1) Единицы измерения
    db.query(SubstanceUnit).filter(SubstanceUnit.type_id == type_id).delete()
    # 2) Поля
    db.query(SubstanceField).filter(SubstanceField.type_id == type_id).delete()
    # 3) Элементы и их зависимости
    items = db.query(SubstanceItem).filter(SubstanceItem.type_id == type_id).all()
    for item in items:
        db.query(SubstanceQuantityChange).filter(SubstanceQuantityChange.item_id == item.id).delete()
        db.query(SubstanceItemComment).filter(SubstanceItemComment.item_id == item.id).delete()
        db.query(SubstanceItemTag).filter(SubstanceItemTag.item_id == item.id).delete()
        db.delete(item)
    # 4) Сам тип
    db.delete(type_obj)
    db.commit()
    # аудит: удаление типа
    write_audit_log(
        method="DELETE",
        path=f"/types/{type_id}",
        user_id=current_user.get("id"),
        email=current_user.get("email"),
        action="DELETE_TYPE",
        entity="substance_type",
        entity_id=type_id,
        details={"type_id": type_id},
    )
    return {"status": "ok"}

@router.get("/types/{type_id}/fields", response_model=List[FieldOut])
def get_fields_by_type_id(type_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    type_instance = db.query(SubstanceType).filter(SubstanceType.id == type_id).first()
    if not type_instance:
        raise HTTPException(status_code=404, detail="Type not found")
    fields = [FieldOut(
        id=f.id, name=f.name, field_type=f.field_type, unit=f.unit, is_required=f.is_required
    ) for f in type_instance.fields]
    return fields

# --- Единицы измерения для типа ---
class UnitIn(BaseModel):
    name: str
    ratio_to_base: float = 1.0
    is_default: bool = False

class UnitOut(BaseModel):
    id: str
    name: str
    ratio_to_base: float
    is_default: bool

@router.get("/types/{type_id}/units", response_model=List[UnitOut])
def list_units(type_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    units = db.query(SubstanceUnit).filter(SubstanceUnit.type_id == type_id).all()
    return [UnitOut(id=u.id, name=u.name, ratio_to_base=u.ratio_to_base, is_default=u.is_default) for u in units]

@router.post("/types/{type_id}/units", response_model=UnitOut)
def add_unit(type_id: str, unit: UnitIn, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    # если помечена как дефолтная — снимем флаг с других
    if unit.is_default:
        db.query(SubstanceUnit).filter(SubstanceUnit.type_id == type_id, SubstanceUnit.is_default == True).update({SubstanceUnit.is_default: False})
    u = SubstanceUnit(id=str(uuid4()), type_id=type_id, name=unit.name, ratio_to_base=unit.ratio_to_base, is_default=unit.is_default)
    db.add(u)
    db.commit()
    db.refresh(u)
    return UnitOut(id=u.id, name=u.name, ratio_to_base=u.ratio_to_base, is_default=u.is_default)

@router.put("/types/{type_id}/units/{unit_id}", response_model=UnitOut)
def update_unit(type_id: str, unit_id: str, unit: UnitIn, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    u = db.query(SubstanceUnit).filter(SubstanceUnit.id == unit_id, SubstanceUnit.type_id == type_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Unit not found")
    if unit.is_default:
        db.query(SubstanceUnit).filter(SubstanceUnit.type_id == type_id, SubstanceUnit.is_default == True).update({SubstanceUnit.is_default: False})
    u.name = unit.name
    u.ratio_to_base = unit.ratio_to_base
    u.is_default = unit.is_default
    db.commit()
    db.refresh(u)
    return UnitOut(id=u.id, name=u.name, ratio_to_base=u.ratio_to_base, is_default=u.is_default)

@router.delete("/types/{type_id}/units/{unit_id}")
def delete_unit(type_id: str, unit_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    u = db.query(SubstanceUnit).filter(SubstanceUnit.id == unit_id, SubstanceUnit.type_id == type_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Unit not found")
    db.delete(u)
    db.commit()
    return {"status": "ok"}

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