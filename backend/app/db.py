from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

url = settings.database_url
if url.startswith("postgres://"):
    url = "postgresql+psycopg://" + url[len("postgres://"):]
elif url.startswith("postgresql://"):
    url = "postgresql+psycopg://" + url[len("postgresql://"):]

if url.startswith("sqlite"):
    _kw = {"connect_args": {"check_same_thread": False}}
else:
    # prepare_threshold=None: safe behind PgBouncer-style poolers (Neon's -pooler endpoint).
    # pool_recycle < 5 min: Neon suspends idle computes after 5 minutes and drops the connections.
    _kw = {"connect_args": {"prepare_threshold": None}, "pool_size": settings.db_pool_size, "max_overflow": settings.db_max_overflow}
engine = create_engine(url, pool_pre_ping=True, pool_recycle=240, **_kw)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    with SessionLocal() as db:
        yield db
