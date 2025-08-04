from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Пример строки подключения для PostgreSQL:
# postgresql://user:password@host:port/dbname
SQLALCHEMY_DATABASE_URL = "postgresql://gen_user:1^GDoFswOw0=).@77.232.135.76:5432/Libsolution"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
