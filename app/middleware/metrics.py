"""
Middleware that records Prometheus metrics for every HTTP request.

Why this reads the route *after* calling the handler:

Starlette resolves which route matched during routing, which happens
inside call_next(). Before that, request.scope has no "route" key —
only the raw path. So the matched APIRoute (and its path template like
/api/v1/weather/{city}/latest) is only readable once the response has
been produced. Reading it too early is the classic mistake that
silently falls back to raw paths — and raw paths as label values mean
one Prometheus time series per city name, typo and scanner probe
(unbounded cardinality).

Requests that match no route (404s from random URLs) get the literal
label "unmatched" — one shared series instead of infinitely many.

The /metrics endpoint itself is excluded: scraping every 5 seconds
would otherwise pollute the request histogram with Prometheus's own
traffic.
"""

import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.routing import Match

from app.metrics import http_request_duration_seconds

METRICS_PATH = "/metrics"


def _route_template(request: Request) -> str:
    """
    Returns the matched route's path template, or "unmatched".

    After call_next(), Starlette stores the matched route in
    request.scope["route"] — an APIRoute whose .path attribute is the
    template string with placeholders intact.
    """
    route = request.scope.get("route")
    if route is not None:
        return route.path
    return "unmatched"


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path == METRICS_PATH:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        http_request_duration_seconds.labels(
            method=request.method,
            route=_route_template(request),
            status=str(response.status_code),
        ).observe(duration)

        return response
