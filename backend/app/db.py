from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

url = settings.database_url
if url.startswith("postgres://"):
    url = "postgresql+psycopg://" + url[len("postgres://"):]
elif url.startswith("postgresql://"):
    url = "postgresql+psycopg://" + url[len("postgresql://"):]

engine = create_engine(
    url,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    with SessionLocal() as db:
        yield db
