from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, JSON, Float, Integer, Table, Text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, UTC

import uuid

SQLALCHEMY_DATABASE_URL = "sqlite:///substance.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

Base = declarative_base()

class User(Base):
    __tablename__ = "user"
    id = Column(String, primary_key=True)  # UUID храним как строку
    username = Column(String, unique=True, nullable=True)  # Логин
    hashed_password = Column(String, nullable=False)  # Пароль (хэш)
    email = Column(String, unique=True, nullable=False)  # Почта
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    # admin = Column(Boolean, default=False, nullable=True)

    permissions = relationship("UserPermission", back_populates="user")

document_tag_table = Table(
    "document_tag", Base.metadata,
    Column("document_id", Integer, ForeignKey("document.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tag.id"), primary_key=True)
)

class Document(Base):
    __tablename__ = "document"
    id = Column(Integer, primary_key=True)
    content = Column(Text, default="")
    filename = Column(String, default="")
    tags = relationship("Tag", secondary=document_tag_table, back_populates="documents")
    # Связь с папкой
    folder_id = Column(Integer, ForeignKey("folder.id"), nullable=True)
    folder = relationship("Folder", back_populates="documents")

class Tag(Base):
    __tablename__ = "tag"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True)
    documents = relationship("Document", secondary=document_tag_table, back_populates="tags")

class Folder(Base):
    __tablename__ = "folder"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    parent_id = Column(Integer, ForeignKey("folder.id"), nullable=True)
    # Вложенные папки
    children = relationship("Folder", backref="parent", remote_side=[id])
    # Журналы (документы) в папке
    documents = relationship("Document", back_populates="folder")

class UserPermission(Base):
    __tablename__ = "user_permission"
    id = Column(String, primary_key=True)  # UUID храним как строку
    user_id = Column(ForeignKey("user.id"))
    entity = Column(String, nullable=False)  # Например: "type", "field", "item", "writeoff"
    can_create = Column(Boolean, default=False)
    can_read = Column(Boolean, default=True)
    can_update = Column(Boolean, default=False)
    can_delete = Column(Boolean, default=False)

    user = relationship("User", back_populates="permissions")

class SubstanceType(Base):
    __tablename__ = "substance_type"
    id = Column(String, primary_key=True)  # UUID храним как строку
    name = Column(String)
    fields = relationship("SubstanceField", back_populates="type")

class SubstanceField(Base):
    __tablename__ = "substance_field"
    id = Column(String, primary_key=True)  # UUID храним как строку
    name = Column(String)
    field_type = Column(String)  # string, int, float, date, enum и т.п.
    unit = Column(String, nullable=True)
    type_id = Column(ForeignKey("substance_type.id"))
    is_required = Column(Boolean, default=False)
    type = relationship("SubstanceType", back_populates="fields")

class SubstanceItem(Base):
    __tablename__ = "substance_item"
    id = Column(String, primary_key=True)  # UUID храним как строку
    type_id = Column(ForeignKey("substance_type.id"))
    name = Column(String)
    data = Column(JSON)  # Словарь вида {"плотность": 1.2, "цвет": "бесцветный"}
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

class SubstanceQuantityChange(Base):
    __tablename__ = "substance_quantity_change"
    id = Column(String, primary_key=True)  # UUID храним как строку
    item_id = Column(ForeignKey("substance_item.id"))
    user_id = Column(ForeignKey("user.id"), nullable=True)  # Кто списал
    change_type = Column(Boolean) # 0 - списание, 1 - пополнение
    amount = Column(Float)
    reason = Column(String, nullable=True)  # Причина списания
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))  # Дата создаётся при первом создании
    item = relationship("SubstanceItem")
    user = relationship("User")

class SubstanceItemComment(Base):
    __tablename__ = "substance_item_comment"
    id = Column(String, primary_key=True)  # UUID храним как строку
    item_id = Column(ForeignKey("substance_item.id"), nullable=False)
    user_id = Column(ForeignKey("user.id"), nullable=True)  # Кто оставил комментарий
    text = Column(String, nullable=False)  # Текст комментария
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    item = relationship("SubstanceItem")
    user = relationship("User")

class SubstanceTag(Base):
    __tablename__ = "substance_tag"
    id = Column(String, primary_key=True)  # UUID храним как строку
    name = Column(String, unique=True, nullable=False)

class SubstanceItemTag(Base):
    __tablename__ = "substance_item_tag"
    id = Column(String, primary_key=True)  # UUID храним как строку
    item_id = Column(ForeignKey("substance_item.id"), nullable=False)
    tag_id = Column(ForeignKey("substance_tag.id"), nullable=False)

    item = relationship("SubstanceItem")
    tag = relationship("SubstanceTag")

class SubstanceChartConfig(Base):
    __tablename__ = "substance_chart_config"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    chart_type = Column(String, nullable=False)
    x_field = Column(String, nullable=False)
    y_fields = Column(JSON, nullable=False)
    filters = Column(JSON, nullable=True)

class ImportTask(Base):
    __tablename__ = "import_task"
    id = Column(String, primary_key=True)  # UUID задачи
    status = Column(String, default="pending")  # pending, running, finished, error
    total = Column(Integer, default=0)  # Всего строк
    imported = Column(Integer, default=0)  # Сколько успешно загружено
    error = Column(Text, nullable=True)  # Сообщение об ошибке (если есть)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    
Base.metadata.create_all(bind=engine)

# --- Добавление тестовых папок и журналов ---
def create_test_folders_and_journals():
    db = SessionLocal()
    try:
        # Проверяем, есть ли уже папки и журналы
        folder_count = db.query(Folder).count()
        doc_count = db.query(Document).count()
        if folder_count == 0 and doc_count == 0:
            # Создаём папки
            folder1 = Folder(name="Папка 1")
            folder2 = Folder(name="Папка 2")
            db.add_all([folder1, folder2])
            db.flush()  # Чтобы получить id

            # Вложенная папка (parent_id указываем явно)
            folder3 = Folder(name="Вложенная папка", parent_id=folder1.id)
            db.add(folder3)
            db.flush()

            # Создаём журналы
            doc1 = Document(filename="Журнал 1", content="Тестовое содержимое 1", folder_id=folder1.id)
            doc2 = Document(filename="Журнал 2", content="Тестовое содержимое 2", folder_id=folder2.id)
            doc3 = Document(filename="Журнал 3", content="Тестовое содержимое 3", folder_id=folder3.id)
            doc4 = Document(filename="Журнал без папки", content="Несортированный журнал", folder_id=None)
            db.add_all([doc1, doc2, doc3, doc4])
            db.commit()
    finally:
        db.close()

create_test_folders_and_journals()
