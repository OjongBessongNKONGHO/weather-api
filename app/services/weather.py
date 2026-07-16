from datetime import datetime, timedelta, UTC
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.models.weather import City, WeatherReading
from app.schemas.weather import WeatherStatsResponse, CityResponse
from app.cache.memory_cache import cache

CACHE_TTL_SECONDS = 300  # 5 minutes — matches the data's real update cadence


async def get_all_cities(db: AsyncSession) -> list[City]:
    """
    Returns all cities ordered alphabetically by name.

    select() replaces db.query() — AsyncSession has no .query() method
    at all, since that legacy API assumes synchronous execution under
    the hood. await db.execute(stmt) runs the query without blocking
    the event loop; .scalars().all() unpacks the result into model
    instances, same as .all() did on the old Query object.
    """
    result = await db.execute(select(City).order_by(City.name))
    return list(result.scalars().all())


async def get_city_by_name(db: AsyncSession, city_name: str) -> City:
    """
    Fetches a single city by name, case-insensitive.

    scalar_one_or_none() replaces .first() — it returns exactly one
    model instance or None, and raises if the query somehow matched
    more than one row (a real bug we'd want to know about, not silently
    hide by taking "the first one").
    """
    result = await db.execute(
        select(City).where(func.lower(City.name) == func.lower(city_name))
    )
    city = result.scalar_one_or_none()
    if not city:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"City '{city_name}' not found. Use GET /api/v1/cities to see available cities.",
        )
    return city


async def get_latest_reading_for_city(db: AsyncSession, city: City) -> WeatherReading:
    """
    Returns the most recent weather reading for a given city.
    """
    result = await db.execute(
        select(WeatherReading)
        .options(selectinload(WeatherReading.city))
        .where(WeatherReading.city_id == city.id)
        .order_by(desc(WeatherReading.recorded_at))
        .limit(1)
    )
    reading = result.scalar_one_or_none()
    if not reading:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No weather data found for '{city.name}'.",
        )
    return reading


async def get_latest_readings_all_cities(
    db: AsyncSession,
    continent: str | None = None,
) -> list[WeatherReading]:
    """
    Returns the most recent reading for every city in a single query.

    The subquery/join structure is unchanged from the sync version —
    select() supports .subquery() and .join() exactly like the old
    Query object did. Only the execution (await db.execute(...)) and
    result unpacking (.scalars().all()) are different.
    """
    cache_key = f"latest_all:{continent or 'all'}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    subquery = (
        select(
            WeatherReading.city_id,
            func.max(WeatherReading.recorded_at).label("max_recorded_at"),
        )
        .group_by(WeatherReading.city_id)
        .subquery()
    )

    stmt = (
        select(WeatherReading)
        .options(selectinload(WeatherReading.city))
        .join(
            subquery,
            (WeatherReading.city_id == subquery.c.city_id)
            & (WeatherReading.recorded_at == subquery.c.max_recorded_at),
        )
    )

    if continent:
        stmt = stmt.join(City, WeatherReading.city_id == City.id).where(
            func.lower(City.continent) == func.lower(continent)
        )

    result = await db.execute(stmt)
    results = list(result.scalars().all())
    cache.set(cache_key, results, ttl_seconds=CACHE_TTL_SECONDS)
    return results


async def get_city_history(
    db: AsyncSession,
    city: City,
    page: int,
    limit: int,
) -> tuple[list[WeatherReading], int]:
    """
    Returns paginated historical readings for a city, newest first.

    The old sync version called base_query.count() directly on the
    Query object. select() has no .count() shortcut, so the count is
    computed by wrapping the same filtered statement in a subquery and
    running SELECT count(*) FROM (...) — one extra query, but it counts
    exactly the same filtered rows the paginated query would return.
    """
    base_stmt = (
        select(WeatherReading)
        .options(selectinload(WeatherReading.city))
        .where(WeatherReading.city_id == city.id)
        .order_by(desc(WeatherReading.recorded_at))
    )

    count_result = await db.execute(
        select(func.count()).select_from(base_stmt.subquery())
    )
    total_count = count_result.scalar_one()

    paged_result = await db.execute(base_stmt.offset((page - 1) * limit).limit(limit))
    readings = list(paged_result.scalars().all())

    return readings, total_count


async def get_city_stats(
    db: AsyncSession,
    city: City,
    days: int,
) -> WeatherStatsResponse:
    """
    Computes aggregated weather statistics for a city over N days.

    All aggregation still happens inside PostgreSQL — Python never
    touches individual readings, exactly as in the sync version.
    """
    if days < 1 or days > 30:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="days must be between 1 and 30.",
        )

    since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)

    stmt = select(
        func.avg(WeatherReading.temperature).label("avg_temperature"),
        func.min(WeatherReading.temperature).label("min_temperature"),
        func.max(WeatherReading.temperature).label("max_temperature"),
        func.avg(WeatherReading.humidity).label("avg_humidity"),
        func.min(WeatherReading.humidity).label("min_humidity"),
        func.max(WeatherReading.humidity).label("max_humidity"),
        func.avg(WeatherReading.wind_speed).label("avg_wind_speed"),
        func.count(WeatherReading.id).label("total_readings"),
    ).where(
        WeatherReading.city_id == city.id,
        WeatherReading.recorded_at >= since,
    )

    result = await db.execute(stmt)
    stats = result.first()

    if not stats or stats.total_readings == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No data found for '{city.name}' in the last {days} days.",
        )

    return WeatherStatsResponse(
        city=CityResponse.model_validate(city),
        days=days,
        avg_temperature=round(stats.avg_temperature, 2),
        min_temperature=round(stats.min_temperature, 2),
        max_temperature=round(stats.max_temperature, 2),
        avg_humidity=round(stats.avg_humidity, 2),
        min_humidity=stats.min_humidity,
        max_humidity=stats.max_humidity,
        avg_wind_speed=round(stats.avg_wind_speed, 2),
        total_readings=stats.total_readings,
    )
