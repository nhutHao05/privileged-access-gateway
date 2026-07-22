from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# Lấy DATABASE_URL từ file config
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Hàm get_db để các Router kết nối DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()