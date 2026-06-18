from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from app.config import settings

# Tells FastAPI to look for the API key in the request header
# under the key "X-API-Key". This is the industry standard header
# name for API key authentication — consumers send every request with:
# X-API-Key: their-secret-key
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """
    Dependency that validates the API key on every protected endpoint.

    FastAPI's Security() works like Depends() but signals to the
    auto-generated /docs that this endpoint requires authentication —
    a lock icon appears next to protected routes in the Swagger UI.

    auto_error=False on the header means FastAPI won't automatically
    reject missing headers — we handle that ourselves below so we can
    return a clear, descriptive error message instead of a generic 403.

    In production you would store hashed API keys in the database and
    look them up here. For this project the key is a single shared
    secret in the environment — straightforward and honest for a
    portfolio API.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key missing. Include your key in the X-API-Key request header.",
        )

    if api_key != settings.api_key_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )

    return api_key
