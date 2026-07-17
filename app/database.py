import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

# The engine is the connection to the database.
# It manages the connection pool — instead of opening a new connection
# for every request (expensive), it keeps a pool of reusable connections.
# pool_pre_ping=True checks if a connection is still alive before using it,
# preventing errors after the database restarts.
#
# create_async_engine (not create_engine) makes every query non-blocking:
# while PostgreSQL is processing a query, this worker is free to handle
# other requests instead of sitting idle waiting on the network round trip.
# pool_size and max_overflow tune a real connection pool - a concept that
# only applies to server-based databases like PostgreSQL. SQLite has no
# such pool (it uses NullPool by default) and rejects these arguments
# outright, which is exactly what broke CI: tests run against SQLite,
# where these two kwargs are meaningless, not just unnecessary.
engine_kwargs = {"pool_pre_ping": True}
if not settings.database_url.startswith("sqlite"):
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_async_engine(settings.database_url, **engine_kwargs)

# async_sessionmaker is the async equivalent of sessionmaker.
# expire_on_commit=False keeps model attributes readable after a commit
# without needing an extra awaited refresh — without this, accessing an
# attribute on an object right after commit() raises an error, because
# SQLAlchemy would normally re-fetch it lazily, which isn't safe to do
# implicitly in async code.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


# Base class for all SQLAlchemy models.
# Every model (table definition) inherits from this. Unchanged from the
# sync version — model declarations don't know or care whether queries
# against them are sync or async.
class Base(DeclarativeBase):
    pass


async def get_db():
    """
    Dependency that provides a database session to each request.

    FastAPI calls this for every request that needs database access.
    'async with' replaces the old try/finally — it opens the session,
    yields it to the request handler, and guarantees it's closed
    afterward even if the request raised an exception.
    """
    async with AsyncSessionLocal() as db:
        yield db
