from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.schemas.weather import HealthResponse
from app.config import settings

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns the API status and database connectivity. No authentication required.",
)
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    """
    Verifies the API is running and the database is reachable.

    Executes a minimal query (SELECT 1) against the database.
    If the database is down, this endpoint returns 'unavailable'
    instead of raising an unhandled exception — giving load balancers
    and monitoring tools a clean signal to route traffic away or
    trigger an alert.

    No API key required — health checks must be accessible to
    infrastructure tooling without credentials.
    """
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "unavailable"

    return HealthResponse(
        status="ok",
        database=db_status,
        version="1.0.0",
        environment=settings.app_env,
    )
