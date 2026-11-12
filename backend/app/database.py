import os
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
else:
    engine = create_engine(
        URL.create(
            "postgresql+psycopg",
            username=os.getenv("POSTGRES_USER", "jobs"),
            password=os.getenv("POSTGRES_PASSWORD", "jobs"),
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "jobsterritory"),
        ),
        pool_pre_ping=True,
    )
DATABASE_URL = engine.url.render_as_string(hide_password=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
