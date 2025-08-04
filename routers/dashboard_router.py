
# Бэкенд для конструктора графиков анализа данных лаборатории

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, JSON
from uuid import uuid4
from auth import get_current_user

# Импорт моделей и зависимостей из основного приложения
from models import (
    SubstanceChartConfig,
    SubstanceItem,
    SubstanceItemTag,
    SubstanceType,
    SubstanceField,
    get_db,
)

router = APIRouter()

# ВАЖНО: Ошибка 422 возникает потому, что в ChartConfig ожидается поле id (обязательное), 
# а на фронте оно не передаётся при создании (POST). 
# При создании id должен генерироваться на сервере, а не требоваться от клиента.
# Нужно сделать id необязательным (Optional) в ChartConfig, чтобы POST работал корректно.

# Модели для графиков

class ChartDataRequest(BaseModel):
    # id вещества, по которому строится график
    item_id: Optional[str] = None
    # id тега, если нужно фильтровать по тегу
    tag_id: Optional[str] = None
    # Тип графика: line, bar, scatter и т.д.
    chart_type: str
    # Ось X: имя поля из data или специальное значение (например, "created_at")
    x_field: str
    # Ось Y: имя поля или список полей из data
    y_fields: List[str]
    # Фильтры (например, {"created_at_from": "...", "created_at_to": "...", "custom_field": value})
    filters: Optional[Dict[str, Any]] = None

class ChartConfig(BaseModel):
    # id теперь необязательный, чтобы не требовать его при создании
    id: Optional[str] = None
    name: str
    chart_type: str
    x_field: str
    y_fields: List[str]
    filters: Optional[Dict[str, Any]] = None

class ChartConfigOut(ChartConfig):
    # Для вывода id будет всегда, но при создании не обязателен
    id: str

class ChartDataOut(BaseModel):
    x: List[Any]
    y: Dict[str, List[Any]]  # ключ - имя поля, значение - список значений
    meta: Optional[Dict[str, Any]] = None

# --- Jinja2 templates ---
templates = Jinja2Templates(directory="templates")
router.mount("/static", StaticFiles(directory="static"), name="static")

@router.get("/dashboard", response_class=HTMLResponse)
def index_dashboard(request: Request, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    return templates.TemplateResponse("pages/index_dashboard.html", {"request": request, "title": "Дэшборд"})

# CRUD для конфигураций графиков
@router.post("/charts/config/", response_model=ChartConfigOut)
def create_chart_config(config: ChartConfig, db: Session = Depends(get_db)):
    db_config = SubstanceChartConfig(
        id=str(uuid4()),
        name=config.name,
        chart_type=config.chart_type,
        x_field=config.x_field,
        y_fields=config.y_fields,
        filters=config.filters
    )
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config

@router.get("/charts/config/", response_model=List[ChartConfigOut])
def list_chart_configs(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    configs = db.query(SubstanceChartConfig).all()
    return configs

@router.get("/charts/config/{config_id}", response_model=ChartConfigOut)
def get_chart_config(config_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    config = db.query(SubstanceChartConfig).filter(SubstanceChartConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Конфигурация графика не найдена")
    return config

@router.delete("/charts/config/{config_id}")
def delete_chart_config(config_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    config = db.query(SubstanceChartConfig).filter(SubstanceChartConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Конфигурация графика не найдена")
    db.delete(config)
    db.commit()
    return {"status": "ok", "message": "Конфигурация графика удалена"}

# Получение данных для построения графика

@router.post("/charts/data/", response_model=ChartDataOut)
def get_chart_data(request: ChartDataRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    Возвращает данные для построения графика по выбранным параметрам.
    Данные берутся из SubstanceItem (data: JSON) и, при необходимости, из других таблиц.
    """
    # Получаем список item_id по фильтру tag_id, если задан
    item_ids = None
    if request.tag_id:
        item_ids = db.query(SubstanceItemTag.item_id).filter(SubstanceItemTag.tag_id == request.tag_id).all()
        item_ids = [row[0] for row in item_ids]
        if not item_ids:
            return ChartDataOut(x=[], y={y: [] for y in request.y_fields}, meta={"chart_type": request.chart_type})

    # Формируем базовый запрос
    query = db.query(SubstanceItem)
    if request.item_id:
        query = query.filter(SubstanceItem.id == request.item_id)
    elif item_ids is not None:
        query = query.filter(SubstanceItem.id.in_(item_ids))

    # Применяем фильтры по дате и по полям data
    if request.filters:
        for key, value in request.filters.items():
            if key == "created_at_from":
                query = query.filter(SubstanceItem.created_at >= value)
            elif key == "created_at_to":
                query = query.filter(SubstanceItem.created_at <= value)
            else:
                # Фильтр по полю в data (JSON)
                query = query.filter(SubstanceItem.data[key].astext == str(value))

    items = query.order_by(SubstanceItem.created_at.asc()).all()

    # Собираем данные для графика
    x_values = []
    y_dict = {y: [] for y in request.y_fields}

    for item in items:
        # Значение по оси X
        if request.x_field in (item.data or {}):
            x_val = item.data.get(request.x_field)
        elif hasattr(item, request.x_field):
            x_val = getattr(item, request.x_field)
        else:
            x_val = None
        x_values.append(x_val)

        # Значения по оси Y
        for y in request.y_fields:
            if y in (item.data or {}):
                y_val = item.data.get(y)
            elif hasattr(item, y):
                y_val = getattr(item, y)
            else:
                y_val = None
            y_dict[y].append(y_val)

    return ChartDataOut(
        x=x_values,
        y=y_dict,
        meta={"chart_type": request.chart_type}
    )

# Метод для получения всех возможных полей для осей и фильтров
@router.get("/charts/fields/", response_model=dict)
def get_chart_fields(type_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    Возвращает список всех возможных полей для построения графиков (оси X, Y, фильтры)
    для выбранного типа вещества.
    """
    type_obj = db.query(SubstanceType).filter(SubstanceType.id == type_id).first()
    if not type_obj:
        raise HTTPException(status_code=404, detail="Тип вещества не найден")

    # Основные поля модели SubstanceItem
    base_fields = [
        {"name": "created_at", "label": "Дата создания", "type": "date"},
        {"name": "updated_at", "label": "Дата изменения", "type": "date"},
        {"name": "name", "label": "Название", "type": "string"},
        {"name": "id", "label": "ID", "type": "string"},
    ]

    # Кастомные поля из таблицы SubstanceField
    custom_fields = []
    for f in type_obj.fields:
        custom_fields.append({
            "name": f.name,
            "label": f.name,
            "type": f.field_type,
            "unit": f.unit,
            "is_required": f.is_required,
        })

    all_fields = base_fields + custom_fields

    return {
        "fields": all_fields
    }
