from models import SessionLocal, Document, Tag

def get_journal_content(journal_id: int):
    db = SessionLocal()
    doc = db.query(Document).filter(Document.id == journal_id).first()
    if not doc:
        doc = Document(id=journal_id, content="")
        db.add(doc)
        db.commit()
        content = ""
    else:
        content = doc.content or ""
    db.close()
    return content

def save_journal_content(journal_id: int, content: str):
    db = SessionLocal()
    doc = db.query(Document).filter(Document.id == journal_id).first()
    if not doc:
        doc = Document(id=journal_id, content=content)
        db.add(doc)
    else:
        doc.content = content
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
