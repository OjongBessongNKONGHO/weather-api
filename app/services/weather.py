from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from fastapi import HTTPException, status
from app.models.weather import City, WeatherReading
from app.schemas.weather import WeatherStatsResponse, CityResponse
from app.cache.memory_cache import cache

CACHE_TTL_SECONDS = 300  # 5 minutes — matches the data's real update cadence


def get_all_cities(db: Session) -> list[City]:
    """
    Returns all cities ordered alphabetically by name.

    Ordering at the database level is always faster than sorting
    in Python — PostgreSQL uses an index on the name column directly.
    """
    return db.query(City).order_by(City.name).all()


def get_city_by_name(db: Session, city_name: str) -> City:
    """
    Fetches a single city by name, case-insensitive.

    func.lower() on both sides means 'paris', 'Paris' and 'PARIS'
    all resolve to the same city. Raises 404 immediately if not found
    so the router never receives a None and has to handle it.
    """
    city = db.query(City).filter(func.lower(City.name) == func.lower(city_name)).first()
    if not city:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"City '{city_name}' not found. Use GET /api/v1/cities to see available cities.",
        )
    return city


def get_latest_reading_for_city(db: Session, city: City) -> WeatherReading:
    """
    Returns the most recent weather reading for a given city.

    Ordered by recorded_at descending, limit 1 — PostgreSQL uses the
    composite index on (city_id, recorded_at) and returns the result
    without scanning the full table.
    """
    reading = (
        db.query(WeatherReading)
        .filter(WeatherReading.city_id == city.id)
        .order_by(desc(WeatherReading.recorded_at))
        .first()
    )
    if not reading:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No weather data found for '{city.name}'.",
        )
    return reading


def get_latest_readings_all_cities(
    db: Session,
    continent: str | None = None,
) -> list[WeatherReading]:
    """
    Returns the most recent reading for every city in a single query.

    Uses a subquery to find the maximum recorded_at per city, then
    joins back to get the full reading row. One round trip to the
    database regardless of how many cities exist.

    An optional continent filter narrows the result to cities on that
    continent only. The filter is applied via a join to City and is
    case-insensitive, matching the same convention used by city name
    lookups elsewhere in this module.
    """
    cache_key = f"latest_all:{continent or 'all'}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    subquery = (
        db.query(
            WeatherReading.city_id,
            func.max(WeatherReading.recorded_at).label("max_recorded_at"),
        )
        .group_by(WeatherReading.city_id)
        .subquery()
    )

    query = db.query(WeatherReading).join(
        subquery,
        (WeatherReading.city_id == subquery.c.city_id)
        & (WeatherReading.recorded_at == subquery.c.max_recorded_at),
    )

    if continent:
        query = query.join(City, WeatherReading.city_id == City.id).filter(
            func.lower(City.continent) == func.lower(continent)
        )

    results = query.all()
    cache.set(cache_key, results, ttl_seconds=CACHE_TTL_SECONDS)
    return results


def get_city_history(
    db: Session,
    city: City,
    page: int,
    limit: int,
) -> tuple[list[WeatherReading], int]:
    """
    Returns paginated historical readings for a city, newest first.

    Pagination avoids returning thousands of rows in a single response.
    offset = (page - 1) * limit moves the database cursor to the right
    starting position. Returns both the data and total_count so the
    caller can compute total_pages without a second query.
    """
    base_query = (
        db.query(WeatherReading)
        .filter(WeatherReading.city_id == city.id)
        .order_by(desc(WeatherReading.recorded_at))
    )

    total_count = base_query.count()
    readings = base_query.offset((page - 1) * limit).limit(limit).all()

    return readings, total_count


def get_city_stats(
    db: Session,
    city: City,
    days: int,
) -> WeatherStatsResponse:
    """
    Computes aggregated weather statistics for a city over N days.

    All aggregation (min, max, avg) happens inside PostgreSQL via
    func.min / func.max / func.avg. The database returns a single row
    with six computed values. Python never touches individual readings.

    days is capped at 30 to prevent expensive queries over very large
    time ranges. A consumer requesting 365 days of minute-level data
    would put serious pressure on the database — the cap keeps queries
    predictable.
    """
    if days < 1 or days > 30:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="days must be between 1 and 30.",
        )

    since = datetime.utcnow() - timedelta(days=days)

    result = (
        db.query(
            func.avg(WeatherReading.temperature).label("avg_temperature"),
            func.min(WeatherReading.temperature).label("min_temperature"),
            func.max(WeatherReading.temperature).label("max_temperature"),
            func.avg(WeatherReading.humidity).label("avg_humidity"),
            func.min(WeatherReading.humidity).label("min_humidity"),
            func.max(WeatherReading.humidity).label("max_humidity"),
            func.avg(WeatherReading.wind_speed).label("avg_wind_speed"),
            func.count(WeatherReading.id).label("total_readings"),
        )
        .filter(
            WeatherReading.city_id == city.id,
            WeatherReading.recorded_at >= since,
        )
        .first()
    )

    if not result or result.total_readings == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No data found for '{city.name}' in the last {days} days.",
        )

    return WeatherStatsResponse(
        city=CityResponse.model_validate(city),
        days=days,
        avg_temperature=round(result.avg_temperature, 2),
        min_temperature=round(result.min_temperature, 2),
        max_temperature=round(result.max_temperature, 2),
        avg_humidity=round(result.avg_humidity, 2),
        min_humidity=result.min_humidity,
        max_humidity=result.max_humidity,
        avg_wind_speed=round(result.avg_wind_speed, 2),
        total_readings=result.total_readings,
    )
