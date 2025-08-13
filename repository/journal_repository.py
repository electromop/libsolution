import re, uuid
from copy import deepcopy
from models import SessionLocal, Document, Tag, DocumentBlock

def get_journal_content(journal_id: int):
    """Возвращает HTML-содержимое журнала, собирая его из блоков."""
    db = SessionLocal()
    # Получаем все блоки, отсортированные по позиции
    blocks = (
        db.query(DocumentBlock)
        .filter(DocumentBlock.document_id == journal_id)
        .order_by(DocumentBlock.position)
        .all()
    )

    if not blocks:
        # Если блоков нет, пробуем вернуть устаревшее содержимое из поля content
        doc = db.query(Document).filter(Document.id == journal_id).first()
        if not doc:
            doc = Document(id=journal_id, filename="")
            db.add(doc)
            db.commit()
            content = ""
        else:
            content = doc.content or ""
    else:
        # Конкатенируем HTML блоков в одно содержимое
        html_parts = []
        for block in blocks:
            # Храним html в поле 'data' (dict) или как строку
            if isinstance(block.data, dict):
                html_parts.append(block.data.get("html", ""))
            else:
                html_parts.append(str(block.data))
        content = "".join(html_parts)

    db.close()
    print(f"\nget_journal_content: {content}")
    return content

def save_journal_content(journal_id: int, content: str):
    """Сохраняет содержимое журнала, разбивая его на блоки.

    Сейчас реализована простая стратегия: HTML разделяется по тегу </p>,
    каждая получившаяся строка считается отдельным блоком с типом "paragraph".
    """
    db = SessionLocal()

    # Гарантируем существование документа
    doc = db.query(Document).filter(Document.id == journal_id).first()
    if not doc:
        doc = Document(id=journal_id, filename="")
        db.add(doc)
        db.flush()  # Чтобы получить id

    # Удаляем старые блоки
    db.query(DocumentBlock).filter(DocumentBlock.document_id == journal_id).delete()

    # Разбиваем контент на параграфы по </p>
    parts = re.split(r"(</p>)", content, flags=re.IGNORECASE)
    current_html = ""
    blocks_html = []
    for part in parts:
        current_html += part
        if part.lower().endswith("</p>"):
            blocks_html.append(current_html)
            current_html = ""
    if current_html.strip():
        blocks_html.append(current_html)

    # Если не удалось разделить, сохраняем один блок
    if not blocks_html:
        blocks_html = [content]

    # Создаём блоки
    for idx, html in enumerate(blocks_html):
        block = DocumentBlock(
            id=str(uuid.uuid4()),
            document_id=doc.id,
            block_type="paragraph",
            data={"html": html},
            position=idx,
        )
        db.add(block)

    # Очищаем устаревшее текстовое поле
    doc.content = ""

    db.commit()
    db.close()

def get_journal_tags(journal_id: int):
    db = SessionLocal()
    doc = db.query(Document).filter(Document.id == journal_id).first()
    tags = [tag.name for tag in doc.tags] if doc else []
    db.close()
    return tags

def add_tag_to_journal(journal_id: int, tag_name: str):
    db = SessionLocal()
    doc = db.query(Document).filter(Document.id == journal_id).first()
    if not doc:
        doc = Document(id=journal_id, content="")
        db.add(doc)
        db.commit()
        db.refresh(doc)
    tag = db.query(Tag).filter(Tag.name == tag_name).first()
    if not tag:
        tag = Tag(name=tag_name)
        db.add(tag)
        db.commit()
        db.refresh(tag)
    if tag not in doc.tags:
        doc.tags.append(tag)
        db.commit()
    db.close()

def get_journal_title(journal_id: int):
    db = SessionLocal()
    doc = db.query(Document).filter(Document.id == journal_id).first()
    if not doc:
        doc = Document(id=journal_id, filename="")
        db.add(doc)
        db.commit()
        title = ""
    else:
        title = doc.filename or ""
    db.close()
    return title

def save_journal_title(journal_id: int, title: str):
    db = SessionLocal()
    doc = db.query(Document).filter(Document.id == journal_id).first()
    if not doc:
        doc = Document(id=journal_id, filename=title)
        db.add(doc)
    else:
        doc.filename = title
    db.commit()
    db.close()

def remove_tag_from_journal(journal_id: int, tag_name: str):
    db = SessionLocal()
    doc = db.query(Document).filter(Document.id == journal_id).first()
    tag = db.query(Tag).filter(Tag.name == tag_name).first()
    if doc and tag and tag in doc.tags:
        doc.tags.remove(tag)
        db.commit()
    db.close()

def get_journal_blocks(journal_id: int):
    """Возвращает список словарей блоков для фронтенда. При первом обращении выполняет миграцию\n    из устаревшего поля content, если блоков ещё нет."""
    db = SessionLocal()
    blocks = (
        db.query(DocumentBlock)
        .filter(DocumentBlock.document_id == journal_id)
        .order_by(DocumentBlock.position)
        .all()
    )
    # --- Lazy migration of legacy content ---
    if not blocks:
        doc = db.query(Document).filter(Document.id == journal_id).first()
        if doc and doc.content:
            save_journal_content(journal_id, doc.content)
            blocks = (
                db.query(DocumentBlock)
                .filter(DocumentBlock.document_id == journal_id)
                .order_by(DocumentBlock.position)
                .all()
            )
    result = []
    for block in blocks:
        data = block.data if isinstance(block.data, dict) else {"html": str(block.data)}
        html = data.get("html", "")
        table = None
        if block.block_type == "table":
            table = data.get("table")
            html = ""  # таблица строится на фронте из JSON
        elif block.block_type == "image":
            image_url = data.get("image_url")
            if image_url:
                html = (
                    "<div class='journal-image-block loading'>"
                    "<div class='journal-image-spinner'></div>"
                    f"<img class='journal-image lazy-image' data-src='{image_url}' alt='' loading='lazy' style='max-width:100%; border-radius:16px; opacity:0;'/>"
                    "</div>"
                )
        result.append({
            "id": block.id,
            "block_type": block.block_type,
            "html": html,
            "table": table,
            "position": block.position,
        })
    db.close()
    return result


def get_journal_blocks_after(journal_id: int, after_position: int):
    """Возвращает блоки с позицией > after_position."""
    db = SessionLocal()
    blocks = (
        db.query(DocumentBlock)
        .filter(
            DocumentBlock.document_id == journal_id,
            DocumentBlock.position > after_position,
        )
        .order_by(DocumentBlock.position)
        .limit(100)
        .all()
    )
    result = []
    for block in blocks:
        data = block.data if isinstance(block.data, dict) else {"html": str(block.data)}
        html = data.get("html", "")
        table = None
        if block.block_type == "table":
            table = data.get("table")
            html = ""
        elif block.block_type == "image":
            image_url = data.get("image_url")
            if image_url:
                html = (
                    "<div class='journal-image-block loading'>"
                    "<div class='journal-image-spinner'></div>"
                    f"<img class='journal-image lazy-image' data-src='{image_url}' alt='' loading='lazy' style='max-width:100%; border-radius:16px; opacity:0;'/>"
                    "</div>"
                )
        result.append({
            "id": block.id,
            "block_type": block.block_type,
            "html": html,
            "table": table,
            "position": block.position,
        })
    db.close()
    return result


def create_journal_block(journal_id: int, after_block_id: str | None, html: str, block_type: str = "paragraph", table: dict | None = None):
    """Создаёт новый блок после указанного блока и возвращает его словарь."""

    db = SessionLocal()

    # Определяем позицию
    if after_block_id:
        after_block = db.query(DocumentBlock).filter(DocumentBlock.id == after_block_id).first()
        position = (after_block.position + 1) if after_block else 0
    else:
        # В конец
        last = (
            db.query(DocumentBlock)
            .filter(DocumentBlock.document_id == journal_id)
            .order_by(DocumentBlock.position.desc())
            .first()
        )
        position = (last.position + 1) if last else 0

    # Сдвигаем все блоки после позиции
    db.query(DocumentBlock).filter(
        DocumentBlock.document_id == journal_id,
        DocumentBlock.position >= position,
    ).update({DocumentBlock.position: DocumentBlock.position + 1})

    # Храним для таблиц только JSON без html
    if block_type == "table":
        payload = {"table": table or {}}
    else:
        payload = {"html": html}
    new_block = DocumentBlock(
        id=str(uuid.uuid4()),
        document_id=journal_id,
        block_type=block_type,
        data=payload,
        position=position,
    )
    db.add(new_block)
    db.commit()

    result = {
        "id": new_block.id,
        "block_type": new_block.block_type,
        "html": "" if block_type == "table" else html,
        "table": table if block_type == "table" else None,
        "position": position,
    }
    db.close()
    return result


def delete_journal_block(block_id: str):
    db = SessionLocal()
    block = db.query(DocumentBlock).filter(DocumentBlock.id == block_id).first()
    if block:
        doc_id = block.document_id
        pos = block.position
        db.delete(block)
        # Сдвинем позиции последующих
        db.query(DocumentBlock).filter(
            DocumentBlock.document_id == doc_id,
            DocumentBlock.position > pos,
        ).update({DocumentBlock.position: DocumentBlock.position - 1})
        db.commit()
    db.close()


def update_journal_block(block_id: str, html: str | None, table: dict | None = None, image_url: str | None = None):
    """Обновляет содержимое блока и возвращает словарь блока для фронтенда.
    Для таблиц сохраняем только JSON; для изображений сохраняем только URL; остальное — html."""
    db = SessionLocal()
    block = db.query(DocumentBlock).filter(DocumentBlock.id == block_id).first()
    updated = None
    if block:
        data: dict = {}
        if block.block_type == "table":
            # Храним только таблицу
            if table is not None:
                data["table"] = table
        elif block.block_type == "image":
            # Храним только URL изображения
            if image_url:
                data["image_url"] = image_url
            # html генерируем при отдаче
            data.setdefault("image_url", (block.data or {}).get("image_url") if isinstance(block.data, dict) else None)
        else:
            # Обычный параграф и пр.: храним html
            data["html"] = html or ""
        block.data = data
        db.commit()
        # Сформируем словарь как в get_journal_blocks
        # Вытаскиваем актуальные данные
        if block.block_type == "table":
            updated = {
                "id": block.id,
                "block_type": block.block_type,
                "html": "<div class='mini-excel-container'></div>",
                "table": block.data.get("table"),
                "position": block.position,
            }
        elif block.block_type == "image":
            url = block.data.get("image_url") if isinstance(block.data, dict) else None
            img_html = (
                "<div class='journal-image-block loading'>"
                "<div class='journal-image-spinner'></div>"
                f"<img class='journal-image lazy-image' data-src='{url}' alt='' loading='lazy' style='max-width:100%; border-radius:16px; opacity:0;'/>"
                "</div>"
            ) if url else ""
            updated = {
                "id": block.id,
                "block_type": block.block_type,
                "html": img_html,
                "table": None,
                "position": block.position,
            }
        else:
            updated = {
                "id": block.id,
                "block_type": block.block_type,
                "html": block.data.get("html") if isinstance(block.data, dict) else str(block.data),
                "table": None,
                "position": block.position,
            }
    db.close()
    return updated


def reorder_journal_blocks(document_id: int, ordered_ids: list[str]):
    """Сохраняет новый порядок блоков по их id. Позиции назначаются по индексу в списке."""
    if not ordered_ids:
        return
    db = SessionLocal()
    try:
        # Присвоим новые позиции согласно порядку
        for idx, bid in enumerate(ordered_ids):
            db.query(DocumentBlock).filter(
                DocumentBlock.document_id == document_id,
                DocumentBlock.id == bid,
            ).update({DocumentBlock.position: idx})
        db.commit()
    finally:
        db.close()


def search_journals(query: str):
    db = SessionLocal()
    # Поиск по названию
    docs_by_title = db.query(Document).filter(Document.filename.like(f"%{query}%")).all()
    journals_by_title = [{"id": doc.id, "filename": doc.filename} for doc in docs_by_title]

    # Поиск по тегам
    tags = db.query(Tag).filter(Tag.name.like(f"%{query}%")).all()
    doc_ids = set()
    journals_by_tags = []
    for tag in tags:
        for doc in tag.documents:
            if doc.id not in doc_ids:
                journals_by_tags.append({"id": doc.id, "filename": doc.filename})
                doc_ids.add(doc.id)
    db.close()
    return {"by_title": journals_by_title, "by_tags": journals_by_tags}


def copy_journal(journal_id: int, new_filename: str | None = None, target_folder_id: int | None = None) -> dict:
    """Создаёт копию журнала: документ, блоки и теги.

    Возвращает словарь с данными нового журнала: {id, filename, folder_id}.
    """
    db = SessionLocal()
    try:
        # Оригинальный документ
        original: Document | None = db.query(Document).filter(Document.id == journal_id).first()
        if original is None:
            raise ValueError("Журнал не найден")

        # Определяем имя и папку для копии
        copy_filename: str = new_filename if (new_filename is not None and new_filename.strip() != "") else f"{original.filename or 'Без названия'} (копия)"
        copy_folder_id: int | None = target_folder_id if target_folder_id is not None else original.folder_id

        # Создаём новый документ
        new_doc = Document(filename=copy_filename, content="", folder_id=copy_folder_id)
        db.add(new_doc)
        db.flush()  # получить id

        # Копируем теги (привязываем существующие Tag к новому документу)
        for tag in list(original.tags or []):
            new_doc.tags.append(tag)

        # Копируем блоки
        blocks = (
            db.query(DocumentBlock)
            .filter(DocumentBlock.document_id == original.id)
            .order_by(DocumentBlock.position)
            .all()
        )
        for blk in blocks:
            payload = deepcopy(blk.data) if isinstance(blk.data, dict) else blk.data
            new_block = DocumentBlock(
                id=str(uuid.uuid4()),
                document_id=new_doc.id,
                block_type=blk.block_type,
                data=payload,
                position=blk.position,
            )
            db.add(new_block)

        # Если блоков нет, но есть устаревшее текстовое содержимое, перенесём его
        if not blocks and (original.content or ""):
            new_doc.content = original.content or ""

        db.commit()
        return {"id": new_doc.id, "filename": new_doc.filename, "folder_id": new_doc.folder_id}
    finally:
        db.close()
