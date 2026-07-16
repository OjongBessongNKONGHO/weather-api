import time
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.schemas.weather import HealthResponse
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns API status, database connectivity and database latency. No authentication required.",
)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """
    Verifies the API is running and the database is reachable.

    Executes a minimal query (SELECT 1) against the database and measures
    the round-trip latency in milliseconds. This distinguishes between a
    database that is reachable but slow and one that is completely down.

    If the database is unreachable, returns database='unavailable' and
    database_latency_ms=None rather than raising an unhandled exception —
    giving load balancers and monitoring tools a clean signal to route
    traffic away or trigger an alert.

    No API key required — health checks must be accessible to
    infrastructure tooling without credentials.
    """
    db_status = "unavailable"
    latency_ms = None
    try:
        start = time.perf_counter()
        await db.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        db_status = "connected"
        logger.debug("Database health check passed in %.2fms", latency_ms)
    except Exception as e:
        logger.error("Database health check failed: %s", e)
    return HealthResponse(
        status="ok",
        database=db_status,
        database_latency_ms=latency_ms,
        version="1.0.0",
        environment=settings.app_env,
    )
