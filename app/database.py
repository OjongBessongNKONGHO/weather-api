from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings


# The engine is the connection to the database.
# It manages the connection pool — instead of opening a new connection
# for every request (expensive), it keeps a pool of reusable connections.
# pool_pre_ping=True checks if a connection is still alive before using it,
# preventing errors after the database restarts.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)


# SessionLocal is a factory that creates database sessions.
# Each request gets its own session — an isolated unit of work.
# autocommit=False means changes are only saved when you explicitly commit.
# autoflush=False means SQLAlchemy won't automatically send pending changes
# to the database before every query — we control when that happens.
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


# Base class for all SQLAlchemy models.
# Every model (table definition) inherits from this.
class Base(DeclarativeBase):
    pass


def get_db():
    """
    Dependency that provides a database session to each request.

    FastAPI's dependency injection calls this function for every request
    that needs database access. The 'yield' turns it into a context manager:
    - Before yield: open the session
    - After yield: close the session (even if an error occurred)

    This guarantees no session is ever left open, preventing connection leaks.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
