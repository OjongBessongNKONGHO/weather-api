import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db
from app.models.weather import City, WeatherReading
from datetime import datetime

# Use an in-memory SQLite database for tests.
# This means tests never touch your real PostgreSQL database —
# each test run starts with a clean slate and leaves nothing behind.
# SQLite is not identical to PostgreSQL but is sufficient for testing
# application logic, query structure and response shapes.
SQLITE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},
)

TestingSessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def override_get_db():
    """
    Replaces the real database session with a test session.
    FastAPI's dependency injection system allows overriding any
    dependency — here we swap get_db() for a version that connects
    to SQLite instead of PostgreSQL. The application code never
    knows the difference.
    """
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """
    Creates all tables once at the start of the test session
    and drops them at the end. scope="session" means this runs
    once for the entire test suite, not once per test.
    autouse=True means every test gets this automatically
    without having to request it explicitly.
    """
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="session")
def db():
    """Provides a database session for fixtures that need to insert data."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="session")
def seed_test_data(db):
    """
    Inserts minimal test data — 2 cities and 3 weather readings.
    scope="session" means this runs once and the data persists
    across all tests. We only need enough data to verify each
    endpoint behaves correctly — not 14,000 rows.
    """
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
    db.commit()
    db.refresh(paris)
    db.refresh(london)

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
            recorded_at=datetime(2026, 6, 18, 19, 0, 0),
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
            recorded_at=datetime(2026, 6, 18, 18, 0, 0),
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
            recorded_at=datetime(2026, 6, 18, 19, 0, 0),
        ),
    ]
    db.add_all(readings)
    db.commit()
    return {"paris": paris, "london": london}


@pytest.fixture(scope="session")
def client(seed_test_data):
    """
    Provides a test HTTP client that talks to the app directly
    in memory — no network, no real server needed.
    TestClient wraps the ASGI app and lets you call endpoints
    exactly like a real HTTP consumer would.
    seed_test_data is listed as a dependency so data is always
    inserted before any test that uses the client runs.
    """
    with TestClient(app) as c:
        yield c


# API key header used in every authenticated request.
# Defined once here so tests don't repeat it.
AUTH_HEADERS = {"X-API-Key": "weather-api-dev-2026"}
