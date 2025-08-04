from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from typing import List, Optional, Literal
from uuid import uuid4

from pydantic import BaseModel
from models import SubstanceType, SubstanceField, get_db
from sqlalchemy.orm import Session

from auth import get_current_user

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

class TypeCreate(BaseModel):
    name: str

class TypeOut(BaseModel):
    id: str
    name: str
    fields: List[FieldCreate]

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
    return TypeOut(id=new_type.id, name=new_type.name, fields=[])

@router.get("/types/", response_model=List[TypeOut])
def list_types(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    types = db.query(SubstanceType).all()
    result = []
    for t in types:
        fields = [FieldCreate(
            name=f.name, field_type=f.field_type, unit=f.unit, is_required=f.is_required
        ) for f in t.fields]
        result.append(TypeOut(id=t.id, name=t.name, fields=fields))
    return result

@router.get("/types/{type_id}/fields", response_model=List[FieldCreate])
def get_fields_by_type_id(type_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    type_instance = db.query(SubstanceType).filter(SubstanceType.id == type_id).first()
    if not type_instance:
        raise HTTPException(status_code=404, detail="Type not found")
    fields = [FieldCreate(
        name=f.name, field_type=f.field_type, unit=f.unit, is_required=f.is_required
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
    return {"status": "ok"}