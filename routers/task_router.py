# --- Импорт веществ из CSV с прогрессом (фоновая задача, прогресс хранится в БД) ---

from fastapi import APIRouter, UploadFile, BackgroundTasks, Form, HTTPException, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from typing import List, Optional
import csv
import io
import uuid
from sqlalchemy import Column, String, Integer, DateTime, Text, inspect
from sqlalchemy.orm import declarative_base
from datetime import datetime, UTC
from models import engine as main_engine, SessionLocal, SubstanceItem, SubstanceQuantityChange, ImportTask, SubstanceUnit, SubstanceItemComment
from pydantic import BaseModel
from auth import get_current_user

router = APIRouter(
    prefix="",
    tags=["import"],
)

# --- Jinja2 templates ---
templates = Jinja2Templates(directory="templates")
router.mount("/static", StaticFiles(directory="static"), name="static")


class ImportTaskOut(BaseModel):
    id: str
    status: str
    total: int
    imported: int
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

def import_items_from_csv_db(file_bytes, db_session_factory, task_id, type_id):
    """
    Фоновая функция для импорта веществ из CSV.
    Прогресс и ошибки пишутся в ImportTask в БД.
    type_id передаётся отдельно, в CSV его нет.
    Если в таблице есть столбец "Количество", то создаётся запись о пополнении.
    Новое: поддерживается столбец единицы количества (например: "Единица", "Ед. изм.", "Unit").
    Количество конвертируется в базовую единицу типа по коэффициенту единицы (ratio_to_base).
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

        # Подготовим справочник единиц для типа
        units = db.query(SubstanceUnit).filter(SubstanceUnit.type_id == type_id).all()
        default_ratio = 1.0
        name_to_ratio = {}
        for u in units:
            if u.is_default:
                default_ratio = u.ratio_to_base or 1.0
            if u.name:
                name_to_ratio[u.name.strip().lower()] = u.ratio_to_base or 1.0

        UNIT_COLS = [
            "Единица", "Ед. изм.", "ед. изм.", "единица",
            "Unit", "UNIT", "unit",
        ]
        COMMENT_COLS = [
            "Комментарий", "комментарий", "Комментарий ", "коммент",
            "Comment", "COMMENT", "comment",
        ]

        for idx, row in enumerate(rows):
            try:
                name = row.get("Название")
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
                    # Собираем все поля кроме name, Количество, колонок единицы и комментария
                    exclude_keys = set(["Название", "Количество"]) | set(UNIT_COLS) | set(COMMENT_COLS)
                    data = {k: v for k, v in row.items() if k not in exclude_keys and v != ""}
                if not name:
                    error_messages.append(f"Строка {idx+1}: не указано имя (Название)")
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
                # Определяем единицу (по имени) из возможных колонок
                unit_name = None
                for col in UNIT_COLS:
                    if col in row and str(row[col]).strip() != "":
                        unit_name = str(row[col]).strip()
                        break
                if qty_value is not None and str(qty_value).strip() != "":
                    try:
                        # поддержаем десятичные запятые
                        qty_str = str(qty_value).replace(',', '.')
                        amount = float(qty_str)
                        # конвертируем в базовую единицу типа
                        ratio = default_ratio
                        if unit_name:
                            ratio = name_to_ratio.get(unit_name.strip().lower(), default_ratio)
                        amount_base = amount * (ratio or 1.0)
                        if amount > 0:
                            new_change = SubstanceQuantityChange(
                                id=str(uuid.uuid4()),
                                item_id=new_item_id,
                                user_id=None,
                                change_type=True,  # True = пополнение
                                amount=amount_base,
                                reason=f"Импорт из CSV{f' ({unit_name})' if unit_name else ''}",
                                created_at=datetime.now(UTC)
                            )
                            db.add(new_change)
                    except Exception as e:
                        error_messages.append(f"Строка {idx+1}: ошибка обработки количества: {e}")
                        # Не прерываем импорт вещества, только не добавляем пополнение

                # Если есть комментарий в одной из колонок, добавим как комментарий к веществу
                comment_text = None
                for col in COMMENT_COLS:
                    if col in row and str(row[col]).strip() != "":
                        comment_text = str(row[col]).strip()
                        break
                if comment_text:
                    new_comment = SubstanceItemComment(
                        id=str(uuid.uuid4()),
                        item_id=new_item_id,
                        user_id=None,
                        text=comment_text,
                        created_at=datetime.now(UTC)
                    )
                    db.add(new_comment)

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

@router.get("/tasks", response_class=HTMLResponse)
def index_task(request: Request, current_user: dict = Depends(get_current_user)):
    return templates.TemplateResponse("pages/index_task.html", {"request": request, "title": "Задачи импорта"})

@router.post("/import/items/", response_model=ImportTaskOut)
async def import_items_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    type_id: str = Form(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Загружает CSV файл с веществами и запускает фоновый импорт.
    type_id передаётся отдельно (выбирается в UI).
    Если в таблице есть столбец "Количество", то создаётся запись о пополнении.
    Возвращает id задачи, по которому можно отслеживать прогресс.
    """
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
    background_tasks.add_task(import_items_from_csv_db, file_bytes, SessionLocal, task_id, type_id)
    return ImportTaskOut(
        id=task_id,
        status="pending",
        total=0,
        imported=0,
        error=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )

@router.get("/import/items/{task_id}", response_model=ImportTaskOut)
def get_import_task_status(task_id: str, current_user: dict = Depends(get_current_user)):
    """
    Получить статус задачи импорта по её id.
    """
    db = SessionLocal()
    try:
        task = db.query(ImportTask).filter(ImportTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Задача не найдена")
        return ImportTaskOut.model_validate(task)
    finally:
        db.close()

@router.get("/import/items/", response_model=List[ImportTaskOut])
def list_import_tasks(current_user: dict = Depends(get_current_user)):
    """
    Получить список всех задач импорта.
    """
    db = SessionLocal()
    try:
        tasks = db.query(ImportTask).order_by(ImportTask.created_at.desc()).all()
        return [ImportTaskOut.model_validate(task) for task in tasks]
    finally:
        db.close()