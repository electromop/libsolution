from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func
from uuid import uuid4
from typing import List, Literal, Optional, Union
from pydantic import BaseModel, Field
from models import SubstanceType, SubstanceField, SubstanceItem, SubstanceQuantityChange, get_db, SubstanceItemComment, SubstanceItemTag, SubstanceTag, SubstanceChartConfig
from datetime import datetime

app = FastAPI()

# CORS (если UI на другом порту)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Jinja2 templates ---
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Эндпоинт для страницы index.html ---

@app.get("/substance", response_class=HTMLResponse)
def index_substance(request: Request, type_id: Optional[str] = None, db: Session = Depends(get_db)):
    if type_id:
        type_obj = db.query(SubstanceType).filter(SubstanceType.id == type_id).first()
        if type_obj:
            return templates.TemplateResponse("pages/index.html", {"request": request, "title": type_obj.name})
        else:
            return templates.TemplateResponse("pages/index.html", {"request": request, "title": "Вещества"})
    else:
        return templates.TemplateResponse("pages/index.html", {"request": request, "title": "Вещества"})

@app.get("/item", response_class=HTMLResponse)
def index_item(request: Request, item_id: Optional[str] = None, db: Session = Depends(get_db)):
    if item_id:
        item_obj = db.query(SubstanceItem).filter(SubstanceItem.id == item_id).first()
        if item_obj:
            return templates.TemplateResponse("pages/index_item.html", {"request": request, "title": item_obj.name})
        else:
            return templates.TemplateResponse("pages/index_item.html", {"request": request, "title": "Вещество не найдено"})
    else:
        return templates.TemplateResponse("pages/index_item.html", {"request": request, "title": "Вещество не найдено"})

@app.get("/tasks", response_class=HTMLResponse)
def index_task(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("pages/index_task.html", {"request": request, "title": "Задачи импорта"})

@app.get("/dashboard", response_class=HTMLResponse)
def index_dashboard(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("pages/index_dashboard.html", {"request": request, "title": "Дэшборд"})

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
class QuantityChangeCreate(BaseModel):
    item_id: str
    change_type: int  # 0 - списание, 1 - пополнение
    amount: float
    reason: Optional[str]  # Причина списания
    created_at: Optional[datetime] = None  # Дата и время изменения количества

class QuantityChangeOut(BaseModel):
    id: str
    item_id: str
    change_type: int  # 0 - списание, 1 - пополнение
    amount: float
    reason: Optional[str]  # Причина списания
    created_at: Optional[datetime] = None  # Дата и время изменения количества
    user_id: Optional[str] = None

    class Config:
        from_attributes = True


# --- API ---

@app.post("/types/", response_model=TypeOut)
def create_type(payload: TypeCreate, db: Session = Depends(get_db)):
    type_id = str(uuid4())
    new_type = SubstanceType(id=type_id, name=payload.name)
    db.add(new_type)
    db.commit()
    db.refresh(new_type)
    return TypeOut(id=new_type.id, name=new_type.name, fields=[])

@app.get("/types/", response_model=List[TypeOut])
def list_types(db: Session = Depends(get_db)):
    types = db.query(SubstanceType).all()
    result = []
    for t in types:
        fields = [FieldCreate(
            name=f.name, field_type=f.field_type, unit=f.unit, is_required=f.is_required
        ) for f in t.fields]
        result.append(TypeOut(id=t.id, name=t.name, fields=fields))
    return result

@app.get("/types/{type_id}/fields", response_model=List[FieldCreate])
def get_fields_by_type_id(type_id: str, db: Session = Depends(get_db)):
    type_instance = db.query(SubstanceType).filter(SubstanceType.id == type_id).first()
    if not type_instance:
        raise HTTPException(status_code=404, detail="Type not found")
    fields = [FieldCreate(
        name=f.name, field_type=f.field_type, unit=f.unit, is_required=f.is_required
    ) for f in type_instance.fields]
    return fields

@app.post("/types/{type_id}/fields")
def add_field(type_id: str, field: FieldCreate, db: Session = Depends(get_db)):
    f = SubstanceField(
        id=str(uuid4()), name=field.name, field_type=field.field_type,
        unit=field.unit, is_required=field.is_required, type_id=type_id
    )
    db.add(f)
    db.commit()
    return {"status": "ok"}

@app.post("/items/", response_model=ItemOut)
def add_item(item: ItemCreate, db: Session = Depends(get_db)):
    new_item = SubstanceItem(id=str(uuid4()), name=item.name, type_id=item.type_id, data=item.data)
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return ItemOut(id=new_item.id, type_id=new_item.type_id, data=new_item.data)






# --- Импорт веществ из CSV с прогрессом (фоновая задача, прогресс хранится в БД) ---

from fastapi import UploadFile, BackgroundTasks, Form
import csv
import io
import threading
import uuid
from sqlalchemy import Column, String, Integer, DateTime, Text
from sqlalchemy.orm import declarative_base
from datetime import datetime, UTC

# --- Модель для отслеживания задач импорта ---
# Лучше вынести в models.py, но для примера определим здесь, если нет в models.py

BaseImportTask = declarative_base()

class ImportTask(BaseImportTask):
    __tablename__ = "import_task"
    id = Column(String, primary_key=True)  # UUID задачи
    status = Column(String, default="pending")  # pending, running, finished, error
    total = Column(Integer, default=0)  # Всего строк
    imported = Column(Integer, default=0)  # Сколько успешно загружено
    error = Column(Text, nullable=True)  # Сообщение об ошибке (если есть)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

# Создаём таблицу, если её нет
from sqlalchemy import inspect
from models import engine as main_engine, SessionLocal, SubstanceItem, SubstanceQuantityChange

def ensure_import_task_table(engine):
    inspector = inspect(engine)
    if "import_task" not in inspector.get_table_names():
        BaseImportTask.metadata.create_all(bind=engine, tables=[ImportTask.__table__])

ensure_import_task_table(main_engine)

def import_items_from_csv_db(file_bytes, db_session_factory, task_id, type_id):
    """
    Фоновая функция для импорта веществ из CSV.
    Прогресс и ошибки пишутся в ImportTask в БД.
    type_id передаётся отдельно, в CSV его нет.
    Если в таблице есть столбец "Количество", то создаётся запись о пополнении.
    """
    db = db_session_factory()
    try:
        task = db.query(ImportTask).filter(ImportTask.id == task_id).first()
        if not task:
            db.close()
            return
        task.status = "running"
        db.commit()

        f = io.StringIO(file_bytes.decode("utf-8"))
        reader = csv.DictReader(f)
        rows = list(reader)
        total = len(rows)
        task.total = total
        db.commit()

        imported = 0
        error_messages = []

        for idx, row in enumerate(rows):
            try:
                name = row.get("name")
                data = {}
                # Если есть столбец data, пробуем его разобрать как JSON, иначе собираем все поля кроме name и Количество
                if "data" in row and row["data"]:
                    import json
                    try:
                        data = json.loads(row["data"])
                    except Exception as e:
                        error_messages.append(f"Строка {idx+1}: ошибка парсинга data: {e}")
                        continue
                else:
                    # Собираем все поля кроме name и Количество
                    data = {k: v for k, v in row.items() if k not in ("name", "Количество") and v != ""}
                if not name:
                    error_messages.append(f"Строка {idx+1}: не указано имя (name)")
                    continue
                # Добавляем вещество
                new_item_id = str(uuid.uuid4())
                new_item = SubstanceItem(
                    id=new_item_id,
                    name=name,
                    type_id=type_id,
                    data=data
                )
                db.add(new_item)
                db.flush()  # Чтобы получить id, если нужно

                # Если есть поле "Количество" и оно не пустое, создаём запись о пополнении
                qty_value = row.get("Количество") or row.get("количество") or row.get("quantity") or row.get("Quantity")
                if qty_value is not None and str(qty_value).strip() != "":
                    try:
                        amount = float(qty_value)
                        if amount > 0:
                            new_change = SubstanceQuantityChange(
                                id=str(uuid.uuid4()),
                                item_id=new_item_id,
                                user_id=None,
                                change_type=True,  # True = пополнение
                                amount=amount,
                                reason="Импорт из CSV",
                                created_at=datetime.now(UTC)
                            )
                            db.add(new_change)
                    except Exception as e:
                        error_messages.append(f"Строка {idx+1}: ошибка обработки количества: {e}")
                        # Не прерываем импорт вещества, только не добавляем пополнение

                imported += 1
                # Периодически коммитим и обновляем прогресс (например, каждые 10)
                if imported % 10 == 0 or idx == total - 1:
                    task.imported = imported
                    task.updated_at = datetime.now(UTC)
                    db.commit()
            except Exception as e:
                error_messages.append(f"Строка {idx+1}: {e}")
        # Финальный коммит
        task.imported = imported
        task.status = "finished" if not error_messages else "error"
        task.error = "\n".join(error_messages) if error_messages else None
        task.updated_at = datetime.now(UTC)
        db.commit()
    except Exception as e:
        # Глобальная ошибка импорта
        task = db.query(ImportTask).filter(ImportTask.id == task_id).first()
        if task:
            task.status = "error"
            task.error = f"Глобальная ошибка: {e}"
            task.updated_at = datetime.now(UTC)
            db.commit()
    finally:
        db.close()

from pydantic import BaseModel

class ImportTaskOut(BaseModel):
    id: str
    status: str
    total: int
    imported: int
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}



@app.post("/import/items/", response_model=ImportTaskOut)
async def import_items_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    type_id: str = Form(...)
):
    """
    Загружает CSV файл с веществами и запускает фоновый импорт.
    type_id передаётся отдельно (выбирается в UI).
    Если в таблице есть столбец "Количество", то создаётся запись о пополнении.
    Возвращает id задачи, по которому можно отслеживать прогресс.
    """
    # Читаем файл в память (можно оптимизировать для больших файлов)
    file_bytes = await file.read()
    task_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        task = ImportTask(
            id=task_id,
            status="pending",
            total=0,
            imported=0,
            error=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        db.add(task)
        db.commit()
    finally:
        db.close()
    # Запускаем фоновую задачу
    background_tasks.add_task(import_items_from_csv_db, file_bytes, SessionLocal, task_id, type_id)
    # Возвращаем информацию о задаче
    return ImportTaskOut(
        id=task_id,
        status="pending",
        total=0,
        imported=0,
        error=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )

@app.get("/import/items/{task_id}", response_model=ImportTaskOut)
def get_import_task_status(task_id: str):
    """
    Получить статус задачи импорта по её id.
    """
    db = SessionLocal()
    try:
        task = db.query(ImportTask).filter(ImportTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Задача не найдена")
        # Используем model_validate вместо from_orm (from_attributes=True)
        return ImportTaskOut.model_validate(task)
    finally:
        db.close()

@app.get("/import/items/", response_model=List[ImportTaskOut])
def list_import_tasks():
    """
    Получить список всех задач импорта.
    """
    db = SessionLocal()
    try:
        tasks = db.query(ImportTask).order_by(ImportTask.created_at.desc()).all()
        # Используем model_validate для каждого объекта
        return [ImportTaskOut.model_validate(task) for task in tasks]
    finally:
        db.close()

from fastapi.responses import JSONResponse

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

@app.get("/items/{item_id}", response_model=ItemOutFull)
def view_item_json(item_id: str, db: Session = Depends(get_db)):
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
from fastapi import Body
from sqlalchemy import and_, func
from typing import Dict, Any

@app.post("/items/filter", response_model=List[ItemOut])
def filter_items(payload: Dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    """w
    Фильтрация items по сложному payload фильтров.
    """
    filters = payload
    query = db.query(SubstanceItem)
    conditions = []

    # Фильтр по имени
    name_mode = filters.get("name_mode")
    name_value = filters.get("name")
    if name_value is not None and name_mode:
        if name_mode == "contains":
            conditions.append(func.lower(SubstanceItem.name).ilike(f"%{name_value.lower()}%"))
        elif name_mode == "equals":
            conditions.append(func.lower(SubstanceItem.name) == name_value.lower())

    # Фильтр по created_at (дата от/до)
    created_at_from = filters.get("field_created_at_date_from")
    created_at_to = filters.get("field_created_at_date_to")
    if created_at_from:
        try:
            dt_from = datetime.fromisoformat(created_at_from)
            conditions.append(SubstanceItem.created_at >= dt_from)
        except Exception:
            pass
    if created_at_to:
        try:
            dt_to = datetime.fromisoformat(created_at_to)
            conditions.append(SubstanceItem.created_at <= dt_to)
        except Exception:
            pass

    # Фильтры по полям data
    for key, value in filters.items():
        if not key.startswith("field_"):
            continue
        # Пропускаем created_at, его уже обработали
        if key.startswith("field_created_at"):
            continue

        # Пример: field_Масса_from, field_Масса_to, field_Опасносить_mode, field_поле 3_mode
        if key.endswith("_from"):
            field_name = key[6:-5]
            try:
                val = float(value)
                # SQLite: json_extract(data, '$."Масса"') >= val
                conditions.append(func.json_extract(SubstanceItem.data, f'$.\"{field_name}\"') >= val)
            except Exception:
                pass
        elif key.endswith("_to"):
            field_name = key[6:-3]
            try:
                val = float(value)
                conditions.append(func.json_extract(SubstanceItem.data, f'$.\"{field_name}\"') <= val)
            except Exception:
                pass
        elif key.endswith("_mode"):
            # обработаем ниже вместе с соответствующим значением
            continue
        else:
            # Это может быть строковое значение для поиска по полю
            field_name = key[6:]
            mode = filters.get(f"field_{field_name}_mode")
            if value is not None and mode:
                json_path = f'$.\"{field_name}\"'
                if mode == "contains":
                    conditions.append(
                        func.lower(func.json_extract(SubstanceItem.data, json_path)).ilike(f"%{str(value).lower()}%")
                    )
                elif mode == "equals":
                    conditions.append(
                        func.lower(func.json_extract(SubstanceItem.data, json_path)) == str(value).lower()
                    )

    if conditions:
        query = query.filter(and_(*conditions))
    return query.all()

@app.get("/items/", response_model=List[ItemOut])
def list_items(type_id: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(SubstanceItem)
    if type_id:
        query = query.filter(SubstanceItem.type_id == type_id)
    return query.all()

# --- Новый эндпоинт для редактирования item ---
@app.put("/items/{item_id}", response_model=ItemOut)
def update_item(item_id: str, item_update: ItemUpdate, db: Session = Depends(get_db)):
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
@app.delete("/items/{item_id}")
def delete_item(item_id: str, db: Session = Depends(get_db)):
    item = db.query(SubstanceItem).filter(SubstanceItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Вещество не найдено")
    db.delete(item)
    db.commit()
    return {"status": "ok", "message": "Вещество удалено"}

# В SQLite функция lower не всегда корректно работает с кириллицей, если не подключено расширение ICU.
# Поэтому для поиска по кириллице делаем двойную проверку: обычный LIKE и lower+LIKE.
# Это увеличивает шанс найти "Бензол" по запросу "бен" или "БЕН".
@app.get("/search/name/", response_model=List[ItemOut])
def search_items_by_name(query: str, db: Session = Depends(get_db)):
    lowered_query = query.lower()
    pattern = f"%{lowered_query}%"
    # Делаем OR: либо совпадение с lower(name), либо с обычным name (на случай, если lower не работает с кириллицей)
    items = db.query(SubstanceItem).filter(
        func.lower(SubstanceItem.name).like(pattern) | SubstanceItem.name.like(f"%{query}%")
    ).all()
    return items

@app.get("/search/data/", response_model=List[ItemOut])
def search_items_by_data(query: str, db: Session = Depends(get_db)):
    # Поиск по всем строковым значениям в data (SQLite: json_each)
    # Используем сырой SQL, чтобы получить id подходящих записей
    from sqlalchemy import text

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



@app.post("/quantity_change", response_model=QuantityChangeOut)
def change_quantity(change: QuantityChangeCreate, db: Session = Depends(get_db)):
    # Проверяем, что вещество существует
    item = db.query(SubstanceItem).filter(SubstanceItem.id == change.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Вещество не найдено")
    from uuid import uuid4
    new_change = SubstanceQuantityChange(
        id=str(uuid4()),
        item_id=change.item_id,
        change_type=change.change_type,
        amount=change.amount,
        reason=change.reason,
        user_id=None  # Можно доработать для поддержки авторизации
    )
    db.add(new_change)
    db.commit()
    db.refresh(new_change)
    return new_change

@app.get("/items/{item_id}/quantity_history", response_model=List[QuantityChangeOut])
def get_quantity_history(item_id: str, db: Session = Depends(get_db)):
    # История изменений количества для вещества
    changes = db.query(SubstanceQuantityChange).filter(SubstanceQuantityChange.item_id == item_id).order_by(SubstanceQuantityChange.created_at.desc()).all()
    return changes

# Работа с комментариями к веществу

from typing import List
from pydantic import BaseModel

class ItemCommentCreate(BaseModel):
    user_id: Optional[str] = None
    text: str

class ItemCommentOut(BaseModel):
    id: str
    item_id: str
    user_id: Optional[str] = None
    text: str
    created_at: datetime

    class Config:
        from_attributes = True

@app.post("/items/{item_id}/comments", response_model=ItemCommentOut)
def add_item_comment(item_id: str, comment: ItemCommentCreate, db: Session = Depends(get_db)):
    from uuid import uuid4
    new_comment = SubstanceItemComment(
        id=str(uuid4()),
        item_id=item_id,
        user_id=comment.user_id,
        text=comment.text
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return new_comment

@app.get("/items/{item_id}/comments", response_model=List[ItemCommentOut])
def get_item_comments(item_id: str, db: Session = Depends(get_db)):
    comments = db.query(SubstanceItemComment).filter(SubstanceItemComment.item_id == item_id).order_by(SubstanceItemComment.created_at.desc()).all()
    return comments

# Работа с тегами

class TagCreate(BaseModel):
    name: str

class TagOut(BaseModel):
    id: str
    name: str

    class Config:
        from_attributes = True

@app.post("/tags/", response_model=TagOut)
def create_tag(tag: TagCreate, db: Session = Depends(get_db)):
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

@app.get("/tags/", response_model=List[TagOut])
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

@app.post("/items/{item_id}/tags/{tag_id}", response_model=ItemTagOut)
def add_tag_to_item(item_id: str, tag_id: str, db: Session = Depends(get_db)):
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

@app.delete("/items/{item_id}/tags/{tag_id}")
def remove_tag_from_item(item_id: str, tag_id: str, db: Session = Depends(get_db)):
    item_tag = db.query(SubstanceItemTag).filter(
        SubstanceItemTag.item_id == item_id,
        SubstanceItemTag.tag_id == tag_id
    ).first()
    if not item_tag:
        raise HTTPException(status_code=404, detail="Связь не найдена")
    db.delete(item_tag)
    db.commit()
    return {"status": "ok", "message": "Тег отвязан от вещества"}

@app.get("/items/{item_id}/tags", response_model=List[TagOut])
def get_tags_for_item(item_id: str, db: Session = Depends(get_db)):
    tags = db.query(SubstanceTag).join(SubstanceItemTag, SubstanceTag.id == SubstanceItemTag.tag_id).filter(
        SubstanceItemTag.item_id == item_id
    ).all()
    return tags



    # Бэкенд для конструктора графиков анализа данных лаборатории

from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from fastapi import Body

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

# Модель для хранения конфигураций графиков (если нужно сохранять)
from sqlalchemy import Column, String, JSON

# CRUD для конфигураций графиков

@app.post("/charts/config/", response_model=ChartConfigOut)
def create_chart_config(config: ChartConfig, db: Session = Depends(get_db)):
    from uuid import uuid4
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

@app.get("/charts/config/", response_model=List[ChartConfigOut])
def list_chart_configs(db: Session = Depends(get_db)):
    configs = db.query(SubstanceChartConfig).all()
    return configs

@app.get("/charts/config/{config_id}", response_model=ChartConfigOut)
def get_chart_config(config_id: str, db: Session = Depends(get_db)):
    config = db.query(SubstanceChartConfig).filter(SubstanceChartConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Конфигурация графика не найдена")
    return config

@app.delete("/charts/config/{config_id}")
def delete_chart_config(config_id: str, db: Session = Depends(get_db)):
    config = db.query(SubstanceChartConfig).filter(SubstanceChartConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Конфигурация графика не найдена")
    db.delete(config)
    db.commit()
    return {"status": "ok", "message": "Конфигурация графика удалена"}

# Получение данных для построения графика

@app.post("/charts/data/", response_model=ChartDataOut)
def get_chart_data(request: ChartDataRequest, db: Session = Depends(get_db)):
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
@app.get("/charts/fields/", response_model=dict)
def get_chart_fields(type_id: str, db: Session = Depends(get_db)):
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
