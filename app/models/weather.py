from datetime import datetime, UTC
from sqlalchemy.orm import relationship
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Index,
    UniqueConstraint,
    ForeignKey,
)
from app.database import Base


class City(Base):
    """
    Represents a city tracked by the API.

    Storing cities in a separate table rather than repeating city metadata
    (country, continent, coordinates) in every weather record keeps the
    schema normalised — city information lives in one place and is referenced
    by weather readings via city_id.
    """

    __tablename__ = "cities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    country = Column(String(100), nullable=False)
    continent = Column(String(50), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    timezone = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class WeatherReading(Base):
    """
    A single weather observation for a city at a point in time.

    Each row is one reading — temperature, humidity, wind speed etc.
    recorded at a specific timestamp. The combination of city_id and
    recorded_at is unique — you cannot have two readings for the same
    city at the same moment.

    Indexes on city_id and recorded_at make the most common queries fast:
    - 'give me all readings for Paris' (city_id lookup)
    - 'give me readings from the last 7 days' (recorded_at range scan)
    """

    __tablename__ = "weather_readings"

    id = Column(Integer, primary_key=True, index=True)
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=False, index=True)
    temperature = Column(Float, nullable=False)
    feels_like = Column(Float, nullable=False)
    humidity = Column(Integer, nullable=False)
    pressure = Column(Integer, nullable=False)
    wind_speed = Column(Float, nullable=False)
    wind_direction = Column(Integer, nullable=False)
    description = Column(String(200), nullable=False)
    cloudiness = Column(Integer, nullable=False)
    visibility = Column(Integer, nullable=False)
    recorded_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None), nullable=False
    )
    city = relationship(
        "City", foreign_keys=[city_id], primaryjoin="WeatherReading.city_id == City.id"
    )

    __table_args__ = (
        # Prevents duplicate readings for the same city at the same time.
        # If the seeder or any ingestion process runs twice, the database
        # rejects the duplicate instead of silently storing it twice.
        UniqueConstraint("city_id", "recorded_at", name="uq_city_reading_time"),
        # Composite index for the most common query pattern:
        # "give me readings for city X ordered by time"
        # Without this index, PostgreSQL would scan every row in the table.
        Index("ix_weather_readings_city_recorded", "city_id", "recorded_at"),
    )
