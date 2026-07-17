from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# Ensure the data directory exists so SQLite can create the file.
os = __import__("os")
os.makedirs(settings.DATA_DIR, exist_ok=True)

db_url = f"sqlite:///{settings.DB_PATH}"
engine = create_engine(
    db_url,
    connect_args={"check_same_thread": False},
    future=True,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
