from fastapi import (
    APIRouter, Request, Form, Depends, WebSocket, WebSocketDisconnect, HTTPException, status
)
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from repository.journal_repository import (
    get_journal_content, get_journal_tags, get_journal_title, save_journal_content,
    add_tag_to_journal, remove_tag_from_journal, save_journal_title, search_journals
)
from models import SessionLocal, Document, Folder
from auth import get_current_user, get_current_user_for_websocket
from connection_manager import manager

router = APIRouter()

templates = Jinja2Templates(directory="templates")

@router.get("/journal/{journal_id}")
async def journal_page(request: Request, journal_id: int, current_user: dict = Depends(get_current_user)):
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

# --- API для получения структуры папок и журналов ---
@router.get("/api/folders")
async def api_get_folders(request: Request, current_user: dict = Depends(get_current_user)):
    """
    Возвращает дерево папок и вложенных журналов для динамического вывода на странице.
    """
    db = SessionLocal()
    folders = db.query(Folder).all()
    unsorted_journals = db.query(Document).filter(Document.folder_id == None).all()

    def build_folder_tree(parent_id=None):
        tree = []
        for folder in [f for f in folders if f.parent_id == parent_id]:
            journals = [
                {"id": doc.id, "filename": doc.filename}
                for doc in folder.documents
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

@router.get("/search")
async def search(query: str, current_user: dict = Depends(get_current_user)):
    results = search_journals(query)
    return JSONResponse(results)

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
    uid, name, color = await manager.connect(websocket, journal_id, current_user["email"])

    await websocket.send_json({
        "type": "init",
        "user_id": uid,
        "name": name,
        "color": color,
        "content": get_journal_content(journal_id),
        "tags": get_journal_tags(journal_id),
        "filename": get_journal_title(journal_id)  # Добавляем название файла при инициализации
    })

    try:
        while True:
            data = await websocket.receive_json()
            if data["type"] == "content":
                save_journal_content(journal_id, data["content"])
                await manager.broadcast(journal_id, {
                    "type": "content",
                    "content": data["content"],
                    "user_id": uid
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
