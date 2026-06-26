from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared limiter instance imported by both main.py and the routers.
# Defined here to avoid circular imports — main.py and weather.py
# both need it, so neither can own it.
limiter = Limiter(key_func=get_remote_address)
