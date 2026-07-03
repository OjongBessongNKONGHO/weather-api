import logging
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs every incoming HTTP request with method, path,
    status code, response time and client IP.

    Attached to the FastAPI app once at startup — every request passes
    through it automatically without any changes to the route handlers.

    Log format:
        METHOD /path STATUS_CODE Xms CLIENT_IP

    Example:
        GET /api/v1/weather/Paris/latest 200 12.3ms 127.0.0.1

    Why response time matters in production:
        A route that normally responds in 5ms suddenly taking 500ms is
        a signal — the database is under pressure, a query is missing
        an index, or an external API is slow. Without timing in the logs
        you only find out when users complain. With timing you catch it
        before it becomes an incident.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.perf_counter()

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start_time) * 1000
        client_ip = request.client.host if request.client else "unknown"

        logger.info(
            "%s %s %d %.1fms %s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            client_ip,
        )

        return response
