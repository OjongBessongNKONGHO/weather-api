from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class CityResponse(BaseModel):
    """
    What the API returns when a consumer asks for city information.

    This is deliberately separate from the SQLAlchemy City model.
    The database model is concerned with storage — the schema is concerned
    with what external consumers see. If you ever add an internal column
    to the City table (an admin flag, a soft-delete field), it stays
    invisible to API consumers because it is never added here.
    """

    id: int
    name: str
    country: str
    continent: str
    latitude: float
    longitude: float
    timezone: str

    model_config = {"from_attributes": True}


class WeatherReadingResponse(BaseModel):
    """
    A single weather reading returned to API consumers.

    Field descriptions feed directly into the auto-generated OpenAPI
    documentation at /docs — consumers see exactly what each field means
    without reading source code.
    """

    id: int
    city_id: int
    temperature: float = Field(description="Temperature in Celsius")
    feels_like: float = Field(description="Perceived temperature in Celsius")
    humidity: int = Field(description="Relative humidity as a percentage (0-100)")
    pressure: int = Field(description="Atmospheric pressure in hPa")
    wind_speed: float = Field(description="Wind speed in metres per second")
    wind_direction: int = Field(description="Wind direction in degrees (0-360)")
    description: str = Field(description="Human-readable weather condition")
    cloudiness: int = Field(description="Cloud cover as a percentage (0-100)")
    visibility: int = Field(description="Visibility in metres")
    recorded_at: datetime
    city: CityResponse

    model_config = {"from_attributes": True}


class WeatherStatsResponse(BaseModel):
    """
    Aggregated statistics for a city over a requested time window.

    min/max/avg computed at the database level — not in Python.
    Pushing aggregation to PostgreSQL means the database returns one row
    instead of potentially thousands of rows that Python would then process.
    """

    city: CityResponse
    days: int = Field(description="Number of days included in the calculation")
    avg_temperature: float
    min_temperature: float
    max_temperature: float
    avg_humidity: float
    min_humidity: int
    max_humidity: int
    avg_wind_speed: float
    total_readings: int


class PaginatedWeatherResponse(BaseModel):
    """
    Wraps a list of weather readings with pagination metadata.

    Returning raw lists without pagination metadata forces consumers to
    guess whether they received all records or just the first page.
    total_count lets consumers calculate how many pages exist.
    page and limit let them know exactly where they are in the dataset.
    """

    data: list[WeatherReadingResponse]
    total_count: int
    page: int
    limit: int
    total_pages: int


class HealthResponse(BaseModel):
    """
    Health check response.

    database_latency_ms measures the round-trip time of a SELECT 1
    query against PostgreSQL. This distinguishes between a database
    that is reachable but slow (high latency) and one that is down
    (unavailable). Load balancers and monitoring tools use this value
    to detect degraded performance before it becomes an outage.
    A None value means the database was unreachable.
    """

    status: str
    database: str
    database_latency_ms: float | None = Field(
        default=None,
        description="Database round-trip latency in milliseconds. None if database is unreachable.",
    )
    version: str
    environment: str
