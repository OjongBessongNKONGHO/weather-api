import asyncio
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.main import app
from app.database import Base, get_db
from app.models.weather import City, WeatherReading
from datetime import datetime, timedelta, UTC

# Use an in-memory-style SQLite database for tests, accessed via aiosqlite.
# This means tests never touch your real PostgreSQL database — each test
# run starts with a clean slate and leaves nothing behind. SQLite is not
# identical to PostgreSQL but is sufficient for testing application logic,
# query structure and response shapes.
SQLITE_URL = "sqlite+aiosqlite:///./test.db"

engine = create_async_engine(SQLITE_URL)

TestingSessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


async def override_get_db():
    """
    Replaces the real database session with a test session.
    Same purpose as the sync version — swap get_db() for one that
    connects to SQLite instead of PostgreSQL — but this override is
    itself an async generator now, matching the real get_db()'s signature.
    """
    async with TestingSessionLocal() as db:
        yield db


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """
    Creates all tables once at the start of the test session and drops
    them at the end. The table creation itself is async work (it awaits
    a real connection), so it's wrapped in asyncio.run() here — pytest
    fixtures are plain sync functions by default, and asyncio.run() is
    the standard way to run a one-off async operation from sync code
    without pulling in pytest-asyncio's async fixture machinery for
    something this simple.
    """

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def _teardown():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    asyncio.run(_setup())
    yield
    asyncio.run(_teardown())


@pytest.fixture(scope="session")
def seed_test_data():
    """
    Inserts minimal test data — 2 cities and 3 weather readings.
    scope="session" means this runs once and the data persists across
    all tests. expire_on_commit=False on the session means paris.id and
    london.id stay readable in the returned dict even after this
    function's session has closed.
    """

    async def _seed():
        async with TestingSessionLocal() as db:
            paris = City(
                name="Paris",
                country="France",
                continent="Europe",
                latitude=48.8566,
                longitude=2.3522,
                timezone="Europe/Paris",
            )
            london = City(
                name="London",
                country="United Kingdom",
                continent="Europe",
                latitude=51.5074,
                longitude=-0.1278,
                timezone="Europe/London",
            )
            db.add_all([paris, london])
            await db.commit()
            await db.refresh(paris)
            await db.refresh(london)

            readings = [
                WeatherReading(
                    city_id=paris.id,
                    temperature=26.1,
                    feels_like=25.8,
                    humidity=76,
                    pressure=1015,
                    wind_speed=3.6,
                    wind_direction=247,
                    description="light rain",
                    cloudiness=100,
                    visibility=10000,
                    recorded_at=datetime.now(UTC).replace(tzinfo=None)
                    - timedelta(hours=1),
                ),
                WeatherReading(
                    city_id=paris.id,
                    temperature=24.5,
                    feels_like=24.0,
                    humidity=70,
                    pressure=1013,
                    wind_speed=2.5,
                    wind_direction=200,
                    description="few clouds",
                    cloudiness=20,
                    visibility=10000,
                    recorded_at=datetime.now(UTC).replace(tzinfo=None)
                    - timedelta(hours=2),
                ),
                WeatherReading(
                    city_id=london.id,
                    temperature=23.6,
                    feels_like=23.1,
                    humidity=65,
                    pressure=1018,
                    wind_speed=4.1,
                    wind_direction=280,
                    description="clear sky",
                    cloudiness=0,
                    visibility=10000,
                    recorded_at=datetime.now(UTC).replace(tzinfo=None)
                    - timedelta(hours=1),
                ),
            ]
            db.add_all(readings)
            await db.commit()
            return {"paris": paris, "london": london}

    return asyncio.run(_seed())


@pytest.fixture(scope="session")
def client(seed_test_data):
    """
    Provides a test HTTP client that talks to the app directly in memory —
    no network, no real server needed. TestClient wraps the ASGI app and
    bridges sync test functions to async routes transparently, so nothing
    in the test files themselves needs to change.
    seed_test_data is listed as a dependency so data is always inserted
    before any test that uses the client runs.
    """
    with TestClient(app) as c:
        yield c


# API key header used in every authenticated request.
# Defined once here so tests don't repeat it.
AUTH_HEADERS = {"X-API-Key": "weather-api-dev-2026"}
