from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
# A handful of endpoints (league-wide averages) hold a session for several
# seconds; the default pool (size 5 + overflow 10) can't absorb a page load
# that fires several of them concurrently plus React StrictMode's double
# effect invocation in dev. SQLite connections are cheap, so size generously.
engine = create_engine(settings.database_url, connect_args=connect_args, pool_size=20, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
