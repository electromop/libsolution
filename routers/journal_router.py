from fastapi import (
    APIRouter, Request, Form, Depends, WebSocket, WebSocketDisconnect, HTTPException, status, UploadFile, File
)
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from repository.journal_repository import (
    get_journal_content, get_journal_tags, get_journal_title, save_journal_content,
    add_tag_to_journal, remove_tag_from_journal, save_journal_title, search_journals,
    get_journal_blocks, update_journal_block, get_journal_blocks_after, create_journal_block, delete_journal_block,
    reorder_journal_blocks, copy_journal,
    set_document_privacy, list_document_access, grant_document_access, revoke_document_access,
    user_can_read_document, user_can_edit_document
)
from models import SessionLocal, Document, Folder, Tag, DocumentSettings, DocumentAccess
from auth import get_current_user, get_current_user_for_websocket
from connection_manager import manager
import os
import uuid
import logging

try:
    import boto3
    from botocore.client import Config as BotoConfig
except Exception:  # fallback if not installed in some environments
    boto3 = None
    BotoConfig = None
try:
    from PIL import Image
except Exception:
    Image = None

router = APIRouter()

templates = Jinja2Templates(directory="templates")

@router.get("/journal/{journal_id}")
async def journal_page(request: Request, journal_id: int, current_user: dict = Depends(get_current_user)):
    # Проверка доступа на чтение
    if not user_can_read_document(current_user["id"], journal_id):
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    content = get_journal_content(journal_id)
    tags = get_journal_tags(journal_id)
    title = get_journal_title(journal_id)
    return templates.TemplateResponse("pages/index_journals.html", {
        "request": request,
        "journal_id": journal_id,
        "content": content,
        "tags": tags,
        "title": title
    })

@router.get("/journals")
async def get_all_journals(request: Request, current_user: dict = Depends(get_current_user)):
    """
    Эндпоинт для отображения страницы журналов.
    Вся загрузка папок и журналов будет происходить через JS (отдельными API).
    """
    return templates.TemplateResponse("pages/index_journals_folder.html", {
        "request": request,
        "title": "Журналы"
    })

# --- Global tags API based on Tag model ---
class TagCreate(BaseModel):
    name: str

class TagOut(BaseModel):
    id: int
    name: str

@router.get("/api/tags", response_model=list[TagOut])
async def api_list_tags(current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        tags = db.query(Tag).order_by(Tag.name.asc()).all()
        return [{"id": t.id, "name": t.name} for t in tags]
    finally:
        db.close()

@router.post("/api/tags", response_model=TagOut)
async def api_create_tag(payload: TagCreate, current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        existing = db.query(Tag).filter(Tag.name == payload.name).first()
        if existing:
            return {"id": existing.id, "name": existing.name}
        t = Tag(name=payload.name)
        db.add(t)
        db.commit()
        db.refresh(t)
        return {"id": t.id, "name": t.name}
    finally:
        db.close()

# --- API для получения структуры папок и журналов ---
@router.get("/api/folders")
async def api_get_folders(request: Request, current_user: dict = Depends(get_current_user)):
    """
    Возвращает дерево папок и вложенных журналов для динамического вывода на странице.
    """
    db = SessionLocal()
    folders = db.query(Folder).all()
    # Фильтруем документы по доступности
    # Публичные или к которым есть доступ для текущего пользователя
    from repository.journal_repository import get_accessible_document_ids
    accessible_ids = get_accessible_document_ids(current_user["id"]) if current_user else set()
    unsorted_journals = db.query(Document).filter(Document.folder_id == None, Document.id.in_(accessible_ids)).all()

    def build_folder_tree(parent_id=None):
        tree = []
        for folder in [f for f in folders if f.parent_id == parent_id]:
            journals = [
                {"id": doc.id, "filename": doc.filename}
                for doc in folder.documents if doc.id in accessible_ids
            ]
            children = build_folder_tree(folder.id)
            tree.append({
                "id": folder.id,
                "name": folder.name,
                "journals": journals,
                "children": children
            })
        return tree

    folder_tree = build_folder_tree()

    # Добавляем "виртуальную" папку для несортированных журналов, если такие есть
    if unsorted_journals:
        folder_tree.insert(0, {
            "id": None,
            "name": "Несортированные",
            "journals": [{"id": doc.id, "filename": doc.filename} for doc in unsorted_journals],
            "children": []
        })

    db.close()
    return JSONResponse(folder_tree)

class CreateFolderPayload(BaseModel):
    name: str
    parent_id: int | None = None

@router.post("/folders/create")
async def create_folder(payload: CreateFolderPayload, current_user: dict = Depends(get_current_user)):
    """
    Эндпоинт для создания новой папки.
    """
    db = SessionLocal()
    folder = Folder(name=payload.name, parent_id=payload.parent_id)
    db.add(folder)
    db.commit()
    db.close()
    return RedirectResponse(url="/journals", status_code=303)

@router.delete("/folders/{folder_id}/delete")
async def delete_folder(folder_id: int, current_user: dict = Depends(get_current_user)):
    """
    Эндпоинт для удаления папки по её ID.
    """
    db = SessionLocal()
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        db.close()
        return JSONResponse({"status": "error", "message": "Папка не найдена"}, status_code=404)
    # Перемещаем все документы из этой папки в несортированные (folder_id=None)
    for doc in folder.documents:
        doc.folder_id = None
    # Перемещаем все дочерние папки на уровень выше (parent_id = parent_id текущей папки)
    for child in db.query(Folder).filter(Folder.parent_id == folder_id).all():
        child.parent_id = folder.parent_id
    db.delete(folder)
    db.commit()
    db.close()
    return JSONResponse({"status": "ok", "message": "Папка удалена"}, status_code=status.HTTP_200_OK)

@router.post("/journals/create")
async def create_journal(filename: str = Form(...), folder_id: int = Form(None), current_user: dict = Depends(get_current_user)):
    """
    Эндпоинт для создания нового журнала в папке (или без папки).
    """
    db = SessionLocal()
    doc = Document(filename=filename, folder_id=folder_id)
    db.add(doc)
    db.commit()
    journal_id = doc.id
    db.close()
    # Создаем новый блок для журнала, используя функцию из репозитория
    create_journal_block(journal_id=journal_id, after_block_id=None, html="", block_type="paragraph")
    # Назначаем владельца/редактора — создателя
    try:
        grant_document_access(journal_id, current_user["id"], can_edit=True, is_owner=True)
    except Exception:
        pass
    return RedirectResponse(url=f"/journal/{journal_id}", status_code=303)

class MoveJournalPayload(BaseModel):
    folder_id: int | None = None

@router.post("/api/journals/{journal_id}/move")
async def move_journal(journal_id: int, payload: MoveJournalPayload, current_user: dict = Depends(get_current_user)):
    """
    Эндпоинт для перемещения журнала в другую папку (или в несортированные).
    folder_id должен передаваться в payload (JSON, через Pydantic).
    """
    db = SessionLocal()
    doc = db.query(Document).filter(Document.id == journal_id).first()
    if not doc:
        db.close()
        return JSONResponse({"status": "error", "message": "Журнал не найден"}, status_code=404)
    doc.folder_id = payload.folder_id
    db.commit()
    db.close()
    return JSONResponse({"status": "ok", "journal_id": journal_id, "folder_id": payload.folder_id})


class CopyJournalPayload(BaseModel):
    filename: str | None = None
    folder_id: int | None = None


@router.post("/api/journals/{journal_id}/copy")
async def api_copy_journal(journal_id: int, payload: CopyJournalPayload, current_user: dict = Depends(get_current_user)):
    """Создать копию журнала с блоками и тегами.
    Опционально можно задать новое имя и целевую папку.
    """
    if not user_can_read_document(current_user["id"], journal_id):
        raise HTTPException(status_code=403, detail="Нет прав")
    try:
        new_doc = copy_journal(journal_id, new_filename=payload.filename, target_folder_id=payload.folder_id)
        return JSONResponse({"status": "ok", "journal": new_doc})
    except ValueError as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=404)
    except Exception:
        # Не палим детали
        return JSONResponse({"status": "error", "message": "Не удалось скопировать журнал"}, status_code=500)

class MoveFolderPayload(BaseModel):
    parent_id: int | None = None

@router.post("/api/folders/{folder_id}/move")
async def move_folder(folder_id: int, payload: MoveFolderPayload, current_user: dict = Depends(get_current_user)):
    """
    Эндпоинт для перемещения папки в другую папку (или на верхний уровень).
    parent_id должен передаваться в payload (JSON, через Pydantic).
    """
    db = SessionLocal()
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        db.close()
        return JSONResponse({"status": "error", "message": "Папка не найдена"}, status_code=404)
    # Проверка на попытку переместить папку саму в себя или в свою под-папку
    if payload.parent_id == folder_id:
        db.close()
        return JSONResponse({"status": "error", "message": "Нельзя переместить папку саму в себя"}, status_code=400)
    # Проверка на циклическое вложение (нельзя переместить в свою под-папку)
    def is_descendant(child_id, target_parent_id):
        if target_parent_id is None:
            return False
        if child_id == target_parent_id:
            return True
        parent = db.query(Folder).filter(Folder.id == target_parent_id).first()
        if parent and parent.parent_id:
            return is_descendant(child_id, parent.parent_id)
        return False
    if payload.parent_id is not None and is_descendant(folder_id, payload.parent_id):
        db.close()
        return JSONResponse({"status": "error", "message": "Нельзя переместить папку в свою под-папку"}, status_code=400)
    folder.parent_id = payload.parent_id
    db.commit()
    db.close()
    return JSONResponse({"status": "ok", "folder_id": folder_id, "parent_id": payload.parent_id})


# --- Upload image to S3 for journal blocks ---
@router.post("/api/journals/{journal_id}/upload_image")
async def upload_journal_image(
    journal_id: int,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    logger = logging.getLogger("upload_image")
    if boto3 is None:
        logger.error("boto3 не установлен")
        raise HTTPException(status_code=500, detail="S3 не настроен на сервере (boto3 не установлен)")

    bucket = os.getenv("S3_BUCKET")
    region = os.getenv("S3_REGION", "us-east-1")
    access_key = os.getenv("S3_ACCESS_KEY_ID")
    secret_key = os.getenv("S3_SECRET_ACCESS_KEY")
    endpoint_url = os.getenv("S3_ENDPOINT_URL")  # можно оставить пустым для AWS

    logger.info(
        "Upload request: journal_id=%s, filename=%s, content_type=%s, env={bucket:%s, region:%s, endpoint:%s, access:%s, secret:%s}",
        journal_id,
        getattr(file, "filename", None),
        getattr(file, "content_type", None),
        bool(bucket),
        region,
        bool(endpoint_url),
        bool(access_key),
        bool(secret_key),
    )

    if not bucket or not access_key or not secret_key:
        logger.error("Отсутствуют переменные окружения S3")
        raise HTTPException(status_code=500, detail="Переменные окружения S3 не заданы: S3_BUCKET, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY")

    try:
        session = boto3.session.Session()
        s3 = session.client(
            "s3",
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            endpoint_url=endpoint_url,
            config=BotoConfig(signature_version="s3v4") if BotoConfig else None,
        )
    except Exception:
        logger.exception("Ошибка инициализации клиента S3")
        raise HTTPException(status_code=500, detail="Ошибка инициализации S3 клиента")

    # Генерируем ключ: journals/{journal_id}/images/{uuid}.{ext}
    filename = file.filename or "image"
    _, ext = os.path.splitext(filename)
    ext = (ext or ".png").lower()
    key = f"journals/{journal_id}/images/{uuid.uuid4().hex}{ext}"

    # Загрузка
    try:
        # Сжатие изображения на лету (если доступна Pillow)
        content_type = file.content_type or "application/octet-stream"
        logger.info("Начало загрузки в S3: bucket=%s, key=%s, content_type=%s", bucket, key, content_type)
        if Image and (content_type.startswith('image/')):
            from io import BytesIO
            raw = await file.read()
            try:
                img = Image.open(BytesIO(raw))
                img = img.convert('RGB') if img.mode in ('RGBA', 'P') else img
                # Лёгкая нормализация размеров до макс ширины 1920px (с сохранением пропорций)
                max_w = int(os.getenv('IMAGE_MAX_WIDTH', '1920'))
                if img.width > max_w:
                    ratio = max_w / float(img.width)
                    new_size = (max_w, int(img.height * ratio))
                    img = img.resize(new_size, Image.LANCZOS)
                # JPEG с разумным качеством 85
                buf = BytesIO()
                img.save(buf, format='JPEG', optimize=True, quality=int(os.getenv('IMAGE_JPEG_QUALITY', '85')))
                buf.seek(0)
                s3.upload_fileobj(buf, bucket, key if key.lower().endswith('.jpg') or key.lower().endswith('.jpeg') else key.rsplit('.',1)[0]+'.jpg',
                                  ExtraArgs={"ContentType": "image/jpeg", "ACL": "public-read"})
                # Если поменяли расширение на jpg — обновим key
                if not (key.lower().endswith('.jpg') or key.lower().endswith('.jpeg')):
                    key = key.rsplit('.',1)[0] + '.jpg'
            except Exception:
                logger.exception('Ошибка сжатия изображения, загружаю оригинал')
                from io import BytesIO
                s3.upload_fileobj(BytesIO(raw), bucket, key, ExtraArgs={"ContentType": content_type, "ACL": "public-read"})
        else:
            # Нет Pillow или неизвестный тип — грузим как есть
            s3.upload_fileobj(file.file, bucket, key, ExtraArgs={"ContentType": content_type, "ACL": "public-read"})
        logger.info("Успешная загрузка в S3: key=%s", key)
    except Exception:
        logger.exception("Ошибка загрузки в S3")
        raise HTTPException(status_code=500, detail="Ошибка загрузки в S3")

    # Формируем публичный URL (для AWS S3 по умолчанию)
    if endpoint_url:
        # Совместимость с S3-совместимыми хранилищами (например, MinIO, Yandex)
        public_url = f"{endpoint_url.rstrip('/')}/{bucket}/{key}"
    else:
        public_url = f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
    logger.info("Готов публичный URL: %s", public_url)
    return JSONResponse({"status": "ok", "url": public_url, "key": key})


# --- Delete journal ---
@router.delete("/api/journals/{journal_id}")
async def api_delete_journal(journal_id: int, current_user: dict = Depends(get_current_user)):
    # if not user_can_edit_document(current_user["id"], journal_id):
    #     raise HTTPException(status_code=403, detail="Нет прав")
    db = SessionLocal()
    try:
        # Удаляем все связанные записи, кроме пользователя
        db.query(DocumentSettings).filter(DocumentSettings.document_id == journal_id).delete()
        db.query(DocumentAccess).filter(DocumentAccess.document_id == journal_id).delete()
        doc = db.query(Document).filter(Document.id == journal_id).first()
        if not doc:
            return JSONResponse({"status": "error", "message": "Журнал не найден"}, status_code=404)
        
        db.delete(doc)
        db.commit()
        return JSONResponse({"status": "ok", "deleted": journal_id})
    finally:
        db.close()

@router.get("/search")
async def search(query: str, current_user: dict = Depends(get_current_user)):
    # Возвращаем только те журналы, которые доступны пользователю
    results = search_journals(query, current_user["id"])
    return JSONResponse(results)

# --- Privacy & Access management ---
class PrivacyPayload(BaseModel):
    is_private: bool

@router.post("/api/journals/{journal_id}/privacy")
async def api_set_privacy(journal_id: int, payload: PrivacyPayload, current_user: dict = Depends(get_current_user)):
    # Только владелец/редактор может менять приватность — упростим: любой с правом редактирования
    if not user_can_edit_document(current_user["id"], journal_id):
        raise HTTPException(status_code=403, detail="Нет прав")
    result = set_document_privacy(journal_id, payload.is_private)
    if "error" in result:
        raise HTTPException(status_code=404, detail="Журнал не найден")
    return JSONResponse(result)

@router.get("/api/journals/{journal_id}/privacy")
async def api_get_privacy(journal_id: int, current_user: dict = Depends(get_current_user)):
    if not user_can_read_document(current_user["id"], journal_id):
        raise HTTPException(status_code=403, detail="Нет прав")
    from models import SessionLocal, DocumentSettings
    db = SessionLocal()
    try:
        settings = db.query(DocumentSettings).filter(DocumentSettings.document_id == journal_id).first()
        is_private = bool(settings.is_private) if settings else False
        return JSONResponse({"document_id": journal_id, "is_private": is_private})
    finally:
        db.close()

@router.get("/api/journals/{journal_id}/access")
async def api_list_access(journal_id: int, current_user: dict = Depends(get_current_user)):
    if not user_can_edit_document(current_user["id"], journal_id):
        raise HTTPException(status_code=403, detail="Нет прав")
    return JSONResponse(list_document_access(journal_id))

class GrantAccessPayload(BaseModel):
    user_id: str
    can_edit: bool = False
    is_owner: bool = False

@router.post("/api/journals/{journal_id}/access")
async def api_grant_access(journal_id: int, payload: GrantAccessPayload, current_user: dict = Depends(get_current_user)):
    if not user_can_edit_document(current_user["id"], journal_id):
        raise HTTPException(status_code=403, detail="Нет прав")
    return JSONResponse(grant_document_access(journal_id, payload.user_id, payload.can_edit, payload.is_owner))

@router.delete("/api/journals/{journal_id}/access/{user_id}")
async def api_revoke_access(journal_id: int, user_id: str, current_user: dict = Depends(get_current_user)):
    if not user_can_edit_document(current_user["id"], journal_id):
        raise HTTPException(status_code=403, detail="Нет прав")
    return JSONResponse(revoke_document_access(journal_id, user_id))

# Поиск пользователей по email/username для выдачи доступа
@router.get("/api/users/search")
async def api_search_users(q: str, current_user: dict = Depends(get_current_user)):
    from models import SessionLocal, User
    db = SessionLocal()
    try:
        query = db.query(User)
        if q:
            like = f"%{q}%"
            query = query.filter((User.email.ilike(like)) | (User.username.ilike(like)))
        users = query.order_by(User.created_at.desc()).limit(20).all()
        return JSONResponse([
            {"id": u.id, "email": u.email, "username": u.username}
            for u in users
        ])
    finally:
        db.close()

@router.post("/journal/{journal_id}/add_tag")
async def add_tag(journal_id: int, tag: str = Form(...), current_user: dict = Depends(get_current_user)):
    add_tag_to_journal(journal_id, tag)
    return JSONResponse({"status": "ok", "tags": get_journal_tags(journal_id)})

@router.post("/journal/{journal_id}/remove_tag")
async def remove_tag(journal_id: int, tag: str = Form(...), current_user: dict = Depends(get_current_user)):
    remove_tag_from_journal(journal_id, tag)
    return JSONResponse({"status": "ok", "tags": get_journal_tags(journal_id)})

@router.get("/journal/{journal_id}/tags")
async def get_tags(journal_id: int, current_user: dict = Depends(get_current_user)):
    tags = get_journal_tags(journal_id)
    return JSONResponse({"tags": tags})

@router.websocket("/ws/journal/{journal_id}")
async def ws_endpoint(websocket: WebSocket, journal_id: int, current_user: dict = Depends(get_current_user_for_websocket)):
    # Проверка доступа на чтение в WS
    try:
        if not user_can_read_document(current_user["id"], journal_id):
            await websocket.close(code=1008)
            return
    except Exception:
        await websocket.close(code=1011)
        return

    uid, name, color = await manager.connect(websocket, journal_id, current_user["email"])

    await websocket.send_json({
        "type": "init",
        "user_id": uid,
        "name": name,
        "color": color,
        "blocks": get_journal_blocks(journal_id),
        "tags": get_journal_tags(journal_id),
        "filename": get_journal_title(journal_id)  # Добавляем название файла при инициализации
    })

    try:
        while True:
            data = await websocket.receive_json()
            if data["type"] == "block_update":
                block_id = data.get("block_id")
                html = data.get("html")
                table_json = data.get("table")
                image_url = data.get("image_url")
                image_width = data.get("image_width")
                if block_id is not None:
                    updated = update_journal_block(block_id, html, table_json, image_url, image_width)
                    if updated:
                        await manager.broadcast(journal_id, {
                            "type": "block_update",
                            "block_id": block_id,
                            "html": updated.get("html", html or ""),
                            "table": updated.get("table"),
                            "user_id": uid,
                        })
                # print(f"block_id: {block_id}, html: {html}")
            elif data["type"] == "block_create":
                after_id = data.get("after_block_id")
                html = data.get("html", "")
                block_type = data.get("block_type", "paragraph")
                table_json = data.get("table")
                new_block = create_journal_block(journal_id, after_id, html, block_type, table_json)
                await manager.broadcast(journal_id, {
                    "type": "block_create",
                    "temp_id": data.get("temp_id"),
                    "block": new_block,
                    "user_id": uid,
                })
            elif data["type"] == "block_delete":
                block_id = data.get("block_id")
                delete_journal_block(block_id)
                await manager.broadcast(journal_id, {
                    "type": "block_delete",
                    "block_id": block_id,
                    "user_id": uid,
                })
            elif data["type"] == "load_blocks":  
                after_pos = data.get("after", -1)
                extra_blocks = get_journal_blocks_after(journal_id, after_pos)
                await websocket.send_json({
                    "type": "blocks",
                    "blocks": extra_blocks,
                })
            elif data["type"] == "block_reorder":
                order = data.get("order", [])
                # Сохраняем порядок
                try:
                    reorder_journal_blocks(journal_id, order)
                except Exception:
                    pass
                # Рассылаем подтверждение нового порядка
                await manager.broadcast(journal_id, {
                    "type": "block_reorder",
                    "order": order,
                    "user_id": uid,
                })
            elif data["type"] == "cursor":
                await manager.broadcast(journal_id, {
                    "type": "cursor",
                    "pos": data["pos"],
                    "user_id": uid
                })
            elif data["type"] == "add_tag":
                tag = data.get("tag")
                if tag:
                    add_tag_to_journal(journal_id, tag)
                    # Оповестим всех о новых тегах
                    await manager.broadcast(journal_id, {
                        "type": "tags",
                        "tags": get_journal_tags(journal_id)
                    })
            elif data["type"] == "remove_tag":
                tag = data.get("tag")
                if tag:
                    remove_tag_from_journal(journal_id, tag)
                    await manager.broadcast(journal_id, {
                        "type": "tags",
                        "tags": get_journal_tags(journal_id)
                    })
            elif data["type"] == "filename":
                filename = data.get("filename")
                if filename is not None:
                    save_journal_title(journal_id, filename)
                    await manager.broadcast(journal_id, {
                        "type": "filename",
                        "filename": filename,
                        "user_id": uid
                    })
    except WebSocketDisconnect:
        manager.disconnect(uid, journal_id)
        await manager.broadcast(journal_id, {
            "type": "leave",
            "user_id": uid
        })
