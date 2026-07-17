"""
Prometheus instruments for the Weather API.

All metrics are defined here in one place — middleware, handlers and
services import from this module rather than defining their own.

Design decisions worth knowing:

Route labels use the *route template* (/api/v1/weather/{city}/latest),
never the raw path (/api/v1/weather/Paris/latest). Prometheus stores
one time series per unique label combination — labelling by raw path
would create a new series for every city name, every typo, and every
scanner probing random URLs (unbounded cardinality, the classic
Prometheus mistake).

Histogram buckets are tuned to this API, not left at the defaults.
The default buckets top out at 10s and waste resolution on ranges this
API never hits. Ours concentrate resolution between 1ms and 1s, which
is where a DB-backed read API actually lives.
"""

from prometheus_client import Counter, Gauge, Histogram

# Request duration by route template, method and status class.
# The histogram also gives request *count* for free via _count.
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds, labelled by route template.",
    ["method", "route", "status"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

# Requests rejected by the per-IP rate limiter (HTTP 429).
rate_limit_rejections_total = Counter(
    "rate_limit_rejections_total",
    "Requests rejected by the rate limiter.",
    ["route"],
)

# Cache effectiveness for the in-memory TTL cache.
# hit/miss ratio tells you whether the 5-minute TTL is actually
# absorbing load or whether every request still reaches PostgreSQL.
cache_operations_total = Counter(
    "cache_operations_total",
    "Cache lookups, labelled by outcome (hit or miss).",
    ["cache_key_prefix", "outcome"],
)

# Connection pool state, read from the engine at scrape time.
# Motivated by a real incident: pool misconfiguration crashed this
# service in production (SQLite rejecting pool_size in CI was the
# same bug from the other side). These gauges make pool exhaustion
# visible *before* requests start queueing.
db_pool_checked_out = Gauge(
    "db_pool_checked_out",
    "Database connections currently in use.",
)

db_pool_size = Gauge(
    "db_pool_size",
    "Database connections currently held open in the pool.",
)
